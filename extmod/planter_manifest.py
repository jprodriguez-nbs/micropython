# This list of frozen files doesn't include task.py because that's provided by the C module.
freeze(
    "..",
    (
        "planter/comm.py",
        "planter/config.py",
        "planter/control_task.py",
        "planter/core.py",
        "planter/display.py",
        "planter/__init__.py",
        "planter/mb_task.py",
        "planter/status.py",
        "planter/test.py",
        "planter/flow.py",
    ),
    opt=3,
)
