# This list of frozen files doesn't include task.py because that's provided by the C module.
freeze(
    "..",
    (
        "primitives/aadc.py",
        "primitives/barrier.py",
        "primitives/condition.py",
        "primitives/delay_ms.py",
        "primitives/encoder.py",
        "primitives/__init__.py",
        "primitives/message.py",
        "primitives/pushbutton.py",
        "primitives/queue.py",
        "primitives/semaphore.py",
        "primitives/switch.py",
    ),
    opt=3,
)
