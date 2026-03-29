#!/bin/sh
PROGDIR=$(cd -P -- "$(dirname $0)" && pwd -P)

# Deploy new configuration
echo "Deploying new configuration"

# System
echo "Changing hostname"
echo "{{ hostname }}" > /proc/sys/kernel/hostname

# Networking
echo "Applying network configuration"
# VPNs
{% for vpn in l2vpn %}
echo "Creating tap {{ vpn.name }}"
openvpn --mktun --dev {{ vpn.name }} --dev-type tap
while [ -z "`grep {{ vpn.name }} /proc/net/dev`" ]; do
  sleep 1
  openvpn --mktun --dev {{ vpn.name }} --dev-type tap
done
{% endfor %}

# Network
echo "Creating bridges"
uci -m import network -f $PROGDIR/uci/network.conf
# ----------- Openwrt boot-bug workaround
vconfig set_name_type DEV_PLUS_VID_NO_PAD
sleep 5
# ----------- Openwrt boot-bug workaround
{% for bridge in bridges %}
echo "Enabling bridge {{ bridge.name }}"
ifup {{ bridge.name }}
{% if bridge.proto == "static" %}
# Waiting for an IP address before starting WiFi configuration:
# For instance if 802.1x is used the IP address to reach the RADIUS server
# could be configured here...
__timeout=10
while [ -z "$(ip address show dev {{ bridge.name }} | grep {{ bridge.ip }})" -o $__timeout -le 0 ]; do
  echo "Waiting for an IP address for bridge {{ bridge.name }}"
  sleep 1
  __timeout=`expr \( $__timeout - 1 \)`
  if [ $__timeout -le 0 ]; then
    echo "Timeout waiting for an IP address on bridge '{{ bridge.name }}'!"
    break
  fi
done
{% endif %}
{% endfor %}

# Wifi
echo "Applying wifi configuration"
uci -m import wireless -f $PROGDIR/uci/wireless.conf
echo "Enabling wifi"
{% for radio in radios %}
wifi up {{ radio.name }}
{% endfor %}

{% if l2vpn %}
# VPNs
echo "Applying l2 vpn(s) configuration"
uci -m import openvpn -f $PROGDIR/uci/openvpn.conf
echo "Enabling l2 vpn(s)"
/etc/init.d/openvpn start
{% endif %}

# Traffic control
echo "Applying tc configuration"
$PROGDIR/tc_script.sh start

{% if cron %}
# cron scripts
mkdir -p $PROGDIR/crontabs
rm $PROGDIR/crond.pid >/dev/null 2>&1
echo "Starting Cron"
start-stop-daemon -m -p /var/run/openwisp_crond.pid -S -b -x crond -- -f -c $PROGDIR/crontabs/ -l 5
{% endif %}

echo "New configuration now active"
