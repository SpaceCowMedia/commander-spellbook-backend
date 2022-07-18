from typing import Optional
from django.db import connection, DEFAULT_DB_ALIAS
from django.db import transaction



def immediate_atomic(using=None, savepoint=True, immediate=True, durable=False):
    # Bare decorator: @atomic -- although the first argument is called
    # `using`, it's actually the function being decorated.
    if callable(using):
        return Atomic(immediate, DEFAULT_DB_ALIAS, savepoint, durable)(using)
    # Decorator: @atomic(...) or context manager: with atomic(...): ...
    else:
        return Atomic(immediate, using, savepoint, durable)

class Atomic(transaction.Atomic):
    def __init__(self, immediate: bool, using: Optional[str], savepoint: bool, durable: bool) -> None:
        super().__init__(using, savepoint, durable)
        self.immediate = immediate

    def __enter__(self):
        connection = transaction.get_connection(self.using)

        if not connection.in_atomic_block:
            # Reset state when entering an outermost atomic block.
            connection.commit_on_exit = True
            connection.needs_rollback = False
            if not connection.get_autocommit():
                # Pretend we're already in an atomic block to bypass the code
                # that disables autocommit to enter a transaction, and make a
                # note to deal with this case in __exit__.
                connection.in_atomic_block = True
                connection.commit_on_exit = False

        if connection.in_atomic_block:
            # We're already in a transaction; create a savepoint, unless we
            # were told not to or we're already waiting for a rollback. The
            # second condition avoids creating useless savepoints and prevents
            # overwriting needs_rollback until the rollback is performed.
            if self.savepoint and not connection.needs_rollback:
                sid = connection.savepoint()
                connection.savepoint_ids.append(sid)
            else:
                connection.savepoint_ids.append(None)
        else:
            if self.immediate:
                connection.set_autocommit(False)
                connection.cursor().execute('BEGIN IMMEDIATE')

            else:
                connection.set_autocommit(False, force_begin_transaction_with_broken_autocommit=True)

            connection.in_atomic_block = True
