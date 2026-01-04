.. _environment_variables:

Environment Variables
=====================

LumiBot supports configuring many behaviors via environment variables. This page documents the variables most commonly used for **backtesting**, **ThetaData**, and **remote caching**.

.. important::

   **Never commit secrets** (API keys, passwords, AWS secret keys) into any repo or docs. Document variable names and semantics only.

Backtesting configuration
------------------------

IS_BACKTESTING
^^^^^^^^^^^^^^

- Purpose: Signals backtesting mode for certain code paths.
- Values: ``True`` / ``False`` (string).

BACKTESTING_START / BACKTESTING_END
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- Purpose: Default date range used when dates are not passed in code.
- Format: ``YYYY-MM-DD``

BACKTESTING_DATA_SOURCE
^^^^^^^^^^^^^^^^^^^^^^^

- Purpose: Select the backtesting datasource **even if your code passes a `datasource_class`**.
- Values (case-insensitive):
  - ``thetadata``, ``yahoo``, ``polygon``, ``alpaca``, ``ccxt``, ``databento``
  - ``none`` to disable the env override and rely on code.

Backtest artifacts + UX flags
-----------------------------

SHOW_PLOT / SHOW_INDICATORS / SHOW_TEARSHEET
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- Purpose: Enable/disable artifact generation.
- Values: ``True`` / ``False`` (string).

BACKTESTING_QUIET_LOGS
^^^^^^^^^^^^^^^^^^^^^^

- Purpose: Reduce log noise during backtests.
- Values: ``true`` / ``false`` (string).

BACKTESTING_SHOW_PROGRESS_BAR
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- Purpose: Enable progress bar updates.
- Values: ``true`` / ``false`` (string).

Trade audit telemetry (accuracy investigations)
-----------------------------------------------

LUMIBOT_BACKTEST_AUDIT
^^^^^^^^^^^^^^^^^^^^^^

- Purpose: Emit **per-fill audit telemetry** into the trade-event CSV as ``audit.*`` columns.
- Values: ``1`` enables (any truthy value); unset/``0`` disables.
- Output:
  - Adds ``audit.*`` columns to the backtest trade-event CSV (for example, quote bid/ask snapshots, bar OHLC, SMART_LIMIT inputs, and multileg linkage).
- Notes:
  - This increases CSV width and can add overhead; keep it enabled only when you need a full audit trail.

Profiling (performance + parity investigations)
------------------------------------------------

BACKTESTING_PROFILE
^^^^^^^^^^^^^^^^^^^

- Purpose: Enable profiling during backtests to attribute runtime (S3 IO vs compute vs artifacts).
- Values:
  - ``yappi`` (supported)
- Output:
  - Produces a ``*_profile_yappi.csv`` artifact alongside other backtest artifacts.

ThetaData via remote downloader
-------------------------------

DATADOWNLOADER_BASE_URL
^^^^^^^^^^^^^^^^^^^^^^^

- Purpose: Points LumiBot at a remote downloader service that can fetch ThetaData on demand.
- Example: ``http://data-downloader.lumiwealth.com:8080``

DATADOWNLOADER_API_KEY / DATADOWNLOADER_API_KEY_HEADER
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- Purpose: Authentication for the downloader service.
- Values: provided by your runtime environment (**do not hardcode**).

Remote cache (S3)
-----------------

LUMIBOT_CACHE_BACKEND / LUMIBOT_CACHE_MODE
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- Purpose: Enable remote cache mirroring (for example, mirroring parquet cache files to S3).
- Common values:
  - ``LUMIBOT_CACHE_BACKEND=s3``
  - ``LUMIBOT_CACHE_MODE=readwrite`` (or ``readonly``)

LUMIBOT_CACHE_FOLDER
^^^^^^^^^^^^^^^^^^^^

- Purpose: Override the local cache folder (useful to simulate a fresh container/task).

LUMIBOT_CACHE_S3_BUCKET / LUMIBOT_CACHE_S3_PREFIX / LUMIBOT_CACHE_S3_REGION
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- Purpose: S3 target configuration.

LUMIBOT_CACHE_S3_VERSION
^^^^^^^^^^^^^^^^^^^^^^^^

- Purpose: Namespace/version the remote cache without deleting anything.
- Practical use: set a unique version to simulate a “cold S3” run safely.

LUMIBOT_CACHE_S3_ACCESS_KEY_ID / LUMIBOT_CACHE_S3_SECRET_ACCESS_KEY / LUMIBOT_CACHE_S3_SESSION_TOKEN
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- Purpose: Credentials for S3 access when not using an instance/task role.
- Values: provided by your runtime environment (**do not hardcode**).

For cache key layout and validation workflow, see :doc:`Backtesting <backtesting>` and the engineering notes in ``docs/remote_cache.md``.
