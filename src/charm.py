#!/usr/bin/env python3
# Copyright 2022 Canonical
# See LICENSE file for licensing details.

"""My ping pong charm!"""

import json
import logging
import time
from typing import Any

from ops.charm import (CharmBase, ActionEvent, ConfigChangedEvent,
                       RelationChangedEvent)
from ops.framework import StoredState
from ops.main import main
from ops.model import ActiveStatus


logger = logging.getLogger(__name__)


class _AdvancedBucket:
    def dumps(self, m: Any) -> str:
        return json.dumps(m)

    def loads(self, m:str) -> Any:
        return json.loads(m)


class FeedAndSyncCharm(CharmBase, _AdvancedBucket):

    _stored = StoredState()
    _MAX_CYCLES_KEY = "max_cycles"
    _DELAY_KEY = "delay"

    def __init__(self, *args):
        super().__init__(*args)
        self.framework.observe(
            self.on.config_changed,
            self._on_config_changed
        )
        self.framework.observe(
            self.on.ping_receive_relation_changed,
            self._on_ping_receive_relation_changed
        )
        self.framework.observe(
            self.on.ping_action,
            self._on_ping_action
        )
        self._stored.set_default(
            bucket={
                self._MAX_CYCLES_KEY: None,
                self._DELAY_KEY: 0
            }
        )
        self.unit.status = ActiveStatus()

    def _on_config_changed(self, event: ConfigChangedEvent) -> None:
        max_cycles = self.config.get("max-cycles")
        delay = self.config.get("delay")

        if max_cycles != self._stored.bucket[self._MAX_CYCLES_KEY]:
            logger.info(f"Updating max cycles to {max_cycles}.")
            self._stored.bucket.update({self._MAX_CYCLES_KEY: max_cycles})
        if delay != self._stored.bucket[self._DELAY_KEY]:
            logger.info(f"Updating total delay to {delay}.")
            self._stored.bucket.update({self._DELAY_KEY: delay})

    def _on_ping_receive_relation_changed(self, event: RelationChangedEvent) -> None:
        """Handler for message is sent over ping-send relation."""
        if (
            "token" not in event.relation.data[event.unit] or 
            event.relation.data[event.unit].get("token") == ""
        ):
            logger.info("Key 'token' is not present or is empty.")
            return
        else:
            logger.info("Key 'token' found. Deserializing...")
            token = self.loads(event.relation.data[event.unit].get("token"))
            max_cycles = self._stored.bucket[self._MAX_CYCLES_KEY]
            delay = self._stored.bucket[self._DELAY_KEY]

            logger.info("Checking cycles complete...")
            if token["origin"] == self.unit.name:
                token["cycles_complete"] += 1
                if token["cycles_complete"] == max_cycles:
                    self.unit.status = ActiveStatus(
                        'Max cycles reached. '
                        +f'Time to completion is {token["time_elapsed"]} seconds.'
                    )
                    return
            
            logger.info("Updating token and sending to next holder...")
            token["times_received"] += 1
            self.unit.status = ActiveStatus(
                f'M: {token["message"]} '
                +f'H: {token["next_holder"]} '
                +f'P: {token["times_passed"]} '
                +f'R: {token["times_received"]} '
                +f'C: {token["cycles_complete"]} '
                +f'T: {token["time_elapsed"]} '
            )
            r = self.model.relations.get("ping-send")[0]
            target = [u.name for u in r.units if u.app is not self.app]
            token["next_holder"] = target[0]
            token["times_passed"] += 1
            timestamp = time.time()
            token["time_elapsed"] += round((timestamp - token["timestamp"]))
            token["timestamp"] = timestamp
            if delay > 0:
                time.sleep(delay)
            self.unit.status = ActiveStatus()
            r.data[self.unit].update(
                {
                    "token": self.dumps(token)
                }
            )

    def _on_ping_action(self, event: ActionEvent) -> None:
        """Handler for when the ping action is invoked."""
        logger.info("Ping action event recieved. Starting...")
        delay = self._stored.bucket[self._DELAY_KEY]
        r = self.model.relations.get("ping-send")[0]
        target = [u.name for u in r.units if u.app is not self.app]

        logger.info("Constructing token...")
        token = {
            "message": event.params["token"],
            "origin": self.unit.name,
            "next_holder": target[0],
            "cycles_complete": 0,
            "times_passed": 0,
            "times_received": 0,
            "time_elapsed": 0,
            "timestamp": round(time.time())
        }
        
        logger.info(f'Sending token to {token["next_holder"]}...')
        token["times_passed"] += 1
        if delay > 0:
            time.sleep(delay)
        r.data[self.unit].update(
            {
                "token": self.dumps(token)
            }
        )
        

if __name__ == "__main__":
    main(FeedAndSyncCharm)
