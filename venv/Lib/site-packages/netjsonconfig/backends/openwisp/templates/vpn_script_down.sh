#!/bin/sh
# When openvpn lost connection restart AP, after config time
# This will place the AP in safemode
REBOOT_ENABLE=`uci -q get owispmanager.vpn_fail.reboot_enabled || echo 0`
REBOOT_DELAY=`uci -q get owispmanager.vpn_fail.reboot_delay || echo 180`
if [ "$REBOOT_ENABLE" -eq "1" ]; then
  touch /tmp/will_reboot
  sleep $REBOOT_DELAY
  if [ -f /tmp/will_reboot ]; then
    reboot
  fi
fi
return 0
