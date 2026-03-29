#!/bin/sh

PROGDIR=$(cd -P -- "$(dirname $0)" && pwd -P)

# Disable traffic control
echo "Removing tc configuration"
$PROGDIR/tc_script.sh stop

# VPNs
echo "Stopping l2 vpn and removing their configuration"
uci changes openvpn | grep "='openvpn" | cut -d'.' -f2 | cut -d'=' -f1 | awk '{print "/var/run/openvpn-"$1".pid"}' | xargs cat | xargs kill
uci changes openvpn | grep "='openvpn" | cut -d'.' -f2 | cut -d'=' -f1 | awk '{"rm /var/run/openvpn-"$1".pid"|getline;print}'
uci revert openvpn

{% for vpn in l2vpn %}
echo "Removing tap {{ vpn.name }}"
openvpn --rmtun --dev {{ vpn.name }} --dev-type tap
{% endfor %}

uci revert wireless
uci revert network

echo "Restoring original wifi and network configurations"
/etc/init.d/network restart
wifi

{% if cron %}
echo "Stopping Cron"
start-stop-daemon -p /var/run/openwisp_crond.pid -K
rm -rf  $PROGDIR/crontabs/
rm /var/run/openwisp_crond.pid
{% endif %}

echo "Configuration un-installed"
