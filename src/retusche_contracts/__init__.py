# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""Types both layers exchange, owned by neither.

Nothing here may import ``retusche`` or ``retusche_worker``. A contract that
reaches back into one of its users stops being a contract.

Nothing here may import a machine-learning runtime either. The orchestration
layer imports this package and runs in the process that listens on a socket.
"""

from retusche_contracts.engine import (
    CancellationToken,
    Cancelled,
    Capabilities,
    DeviceMemoryEstimate,
    EditRequest,
    Engine,
    EngineError,
    EngineFailure,
    ImageBuffer,
    JobDescription,
    MaskBuffer,
    ModelNotAvailable,
    Operation,
    OutOfDeviceMemory,
    ProgressCallback,
    SizeConstraint,
    UnsupportedRequest,
)

__all__ = [
    "CancellationToken",
    "Cancelled",
    "Capabilities",
    "DeviceMemoryEstimate",
    "EditRequest",
    "Engine",
    "EngineError",
    "EngineFailure",
    "ImageBuffer",
    "JobDescription",
    "MaskBuffer",
    "ModelNotAvailable",
    "Operation",
    "OutOfDeviceMemory",
    "ProgressCallback",
    "SizeConstraint",
    "UnsupportedRequest",
]
