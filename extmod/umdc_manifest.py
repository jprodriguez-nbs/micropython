# This list of frozen files doesn't include task.py because that's provided by the C module.
freeze(
    "..",
    (
        "umdc/comm.py",
        "umdc/core.py",
        "umdc/mb_task.py",
        "umdc/mqtt_task.py",
        "umdc/__init__.py",
        "umdc/status.py"
    ),
    opt=3,
)
