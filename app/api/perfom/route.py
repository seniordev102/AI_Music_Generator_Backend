import time

import numpy as np
from fastapi import APIRouter, Query
from pydantic import BaseModel

router = APIRouter()


class ComputationResult(BaseModel):
    result: float
    execution_time: float


def perform_intensive_computation(
    size: int = 1000, iterations: int = 100
) -> tuple[float, float]:
    """
    Performs CPU-intensive matrix operations.
    Returns the result and execution time.
    """
    start_time = time.time()

    # Generate large random matrices
    matrix1 = np.random.rand(size, size)
    matrix2 = np.random.rand(size, size)

    result = 0
    # Perform multiple matrix multiplications
    for _ in range(iterations):
        # Matrix multiplication
        temp = np.matmul(matrix1, matrix2)
        # Add some additional operations
        result += np.sum(np.sin(temp)) + np.sum(np.cos(temp))
        # Rotate matrices slightly to prevent optimization
        matrix1 = np.roll(matrix1, 1, axis=0)
        matrix2 = np.roll(matrix2, 1, axis=1)

    execution_time = time.time() - start_time
    return float(result), execution_time


@router.get("/cpu-test", response_model=ComputationResult)
async def cpu_intensive_task(
    matrix_size: int = Query(default=1000, ge=100, le=2000),
    iterations: int = Query(default=100, ge=1, le=500),
) -> ComputationResult:
    """
    A CPU-intensive endpoint that performs matrix operations.

    Parameters:
    - matrix_size: Size of the square matrices (NxN). Default 1000, min 100, max 2000
    - iterations: Number of matrix multiplication iterations. Default 100, min 1, max 500

    Returns:
    - result: Final computed value
    - execution_time: Time taken for computation in seconds
    """
    result, execution_time = perform_intensive_computation(matrix_size, iterations)
    return ComputationResult(result=result, execution_time=execution_time)
