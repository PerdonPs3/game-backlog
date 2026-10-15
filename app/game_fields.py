from datetime import date


STATUSES = ("Backlog", "Playing", "Completed", "On hold", "Dropped")


def validate_dates(started_on, completed_on):
    for value in (started_on, completed_on):
        if value is None:
            continue
        try:
            if len(value) != 10 or date.fromisoformat(value).isoformat() != value:
                raise ValueError
        except (TypeError, ValueError):
            return "Please enter valid dates in YYYY-MM-DD format."
    if started_on and completed_on and completed_on < started_on:
        return "Completion date cannot be earlier than start date."
    return None
