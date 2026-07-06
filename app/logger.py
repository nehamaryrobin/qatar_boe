import logging

def get_logger(name: str) -> logging.Logger:

    logger = logging.getLogger(name)
    
    # If logger already configured, return it
    if logger.handlers:
        return logger

    # Configure default handler and level
    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # ── Console handler ───────────────────────────────────────────────────────
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)

    # ── Database handler ──────────────────────────────────────────────────────
    try:
        from app.db_log_handler import DBLogHandler
        db_handler = DBLogHandler()
        db_handler.setLevel(logging.DEBUG)
        logger.addHandler(db_handler)
    except ImportError:
        pass

    logger.addHandler(ch)

    return logger