{% block head %} {{ notification.level }} : {{notification.target}} {{ notification.verb }} {% endblock head %}
{% block body %}
{% if notification.actor_link %}[{{notification.actor}}]({{notification.actor_link}}){% else %}{{notification.actor}}{% endif %}
reports
{% if notification.target_link %}[{{notification.target}}]({{notification.target_link}}){% else %}{{notification.target}}{% endif %}
{{ notification.verb }}.
{% endblock body %}
