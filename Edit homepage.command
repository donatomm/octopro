#!/bin/zsh
# The editor normally runs in the background (com.donato.octopro-editor). This just opens it.
if ! curl -s -o /dev/null http://127.0.0.1:8790/; then
  launchctl kickstart -k gui/$(id -u)/com.donato.octopro-editor 2>/dev/null; sleep 2
fi
open http://127.0.0.1:8790/
