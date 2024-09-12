# This list of frozen files doesn't include task.py because that's provided by the C module.
freeze(
    "mqtt_as",
    (
        "mqtt_as.py",
        "mqtt_as_timeout.py"
    ),
    opt=3,
)

