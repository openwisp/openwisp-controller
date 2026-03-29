#!/bin/sh /etc/rc.common

KERNEL_VERSION=`uname -r`
KERNEL_MODULES="sch_htb sch_prio sch_sfq cls_fw sch_dsmark sch_ingress sch_tbf sch_red sch_hfsc act_police cls_tcindex cls_flow cls_route cls_u32"
KERNEL_MPATH=/lib/modules/$KERNEL_VERSION/

TC_COMMAND=/usr/sbin/tc

check_prereq() {
    echo "Checking prerequisites..."

    echo "Checking kernel modules..."
    for kmod in $KERNEL_MODULES; do
    if [ ! -f $KERNEL_MPATH/$kmod.ko ]; then
        echo "Prerequisite error: can't find kernel module '$kmod' in '$KERNEL_MPATH'"
        exit 1
    fi
    done

    echo "Checking tc tool..."
    if [ ! -x $TC_COMMAND ]; then
        echo "Prerequisite error: can't find traffic control tool ($TC_COMMAND)"
        exit 1
    fi

    echo "Prerequisites satisfied."
}

load_modules() {
    for kmod in $KERNEL_MODULES; do
        insmod $KERNEL_MPATH/$kmod.ko  >/dev/null 2>&1
    done
}

unload_modules() {
    for kmod in $KERNEL_MODULES; do
        rmmod $kmod  >/dev/null 2>&1
    done
}


stop() {
{% for interface in tc_options %}
    {% if interface.output_bandwidth %}

    tc qdisc del dev {{ interface.name }} root

    {% endif %}
    {% if interface.input_bandwidth %}

    tc qdisc del dev {{ interface.name }} ingress

    {% endif %}
{% endfor %}

    unload_modules
}

start() {
    check_prereq
    load_modules

{% for interface in tc_options %}
    {% if interface.output_bandwidth %}

    # shaping output traffic for {{ interface.name }}
    # creating parent qdisc for root
    tc qdisc add dev {{ interface.name }} root handle 1: htb default 2

    # aggregated traffic shaping parent class
    {# 0.187*X is calculated as 1.5*X/8 (as stated here: https://learningnetwork.cisco.com/thread/24611) #}
    {% set burst_rate = (0.187 * interface.output_bandwidth) %}

    tc class add dev {{ interface.name }} parent 1 classid 1:1 htb rate {{ interface.output_bandwidth }}kbit burst {{ burst_rate|round|int }}k

    {% set divided_rate = (interface.output_bandwidth / 2) %}

    # default traffic shaping class
    tc class add dev {{ interface.name }} parent 1:1 classid 1:2 htb rate {{ divided_rate|round|int }}kbit ceil {{ interface.output_bandwidth }}kbit

    {#
    # specific ToS traffic shaping (for each ToS specify a filter with specific preference,
    # the highest the best, and increment flowid by 2, classid for relative class is equal to flowid +1)
    tc filter add dev <device> parent 1:1 protocol ip preference <upload filter rule preference> u32 match ip tos <tos> <tos mask> flowid <upload flowid>
    tc class add dev <device> parent < upload flowid> classid <upload classid> htb rate <custom class upload minimum bandwidth>kbit ceil <custom class upload maximum bandwidth>kbit
    #}
    {% endif %}
    {% if interface.input_bandwidth %}

    # policing input traffic for {{ interface.name }}
    # creating parent qdisc for ingress
    tc qdisc add dev {{ interface.name }} ingress

    {% set burst_rate = (0.187 * interface.input_bandwidth) %}

    # default policer with lowest preference (last checked)
    tc filter add dev {{ interface.name }} parent ffff: preference 0 u32 match u32 0x0 0x0 police rate {{ interface.input_bandwidth }}kbit burst {{ burst_rate|round|int }}k drop flowid :1
    {#
    # specific ToS policing (select preference, the higher the first, Tos, policing and flowid)
    tc filter add dev <device> parent ffff: protocol ip preference <download filter rule preference> u32 match ip tos <tos> <tos mask> police rate <custom download police bandwidth>kbit burst <custom download police burst>k drop flowid <download flowid>
    #}
    {% endif %}
{% endfor %}

}

boot() {
    start
}

restart() {
    stop
    start
}
