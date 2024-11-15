# Subscription Credit Management Tests

This directory contains tests for the subscription credit management system, focusing on subscription renewals and credit rollovers.

## Test Structure

- **Unit Tests**: Located in `tests/unit/` - Test individual components in isolation with mocks
- **Integration Tests**: Located in `tests/` - Test multiple components working together

## Key Test Files

- `tests/unit/api/credit_management/stripe/test_subscription_renewal.py`: Tests for basic subscription renewal functionality
- `tests/unit/api/credit_management/stripe/test_multiple_renewals.py`: Tests for multiple renewals with rollover credits
- `tests/integration_test_subscription_renewal.py`: Integration tests for the entire renewal flow

## Running Tests

### Running All Tests

```bash
poetry run pytest
```

### Running Specific Test Files

```bash
# Run unit tests for subscription renewal
poetry run pytest tests/unit/api/credit_management/stripe/test_subscription_renewal.py

# Run multiple renewals tests
poetry run pytest tests/unit/api/credit_management/stripe/test_multiple_renewals.py

# Run integration tests
poetry run pytest tests/integration_test_subscription_renewal.py
```

### Running Tests with Coverage

```bash
poetry run pytest --cov=app.api.credit_management
```

To generate an HTML coverage report:

```bash
poetry run pytest --cov=app.api.credit_management --cov-report=html
```

## Test Scenarios

The tests cover the following key scenarios:

1. **Basic Subscription Renewal**

   - New subscription without existing credits
   - Renewal with rollover credits
   - Proper transaction and balance record creation

2. **Monthly Credit Allocation for Yearly Subscriptions**

   - Correct allocation of monthly credits
   - Idempotency checks to prevent duplicate allocations
   - Rollover handling for monthly allocations

3. **Credit Expiration Handling**

   - Expired credits are not included in rollover
   - Rollover credits receive a new expiration date
   - Only unexpired credits are considered for rollover

4. **Multiple Renewals**

   - Correct handling of multiple consecutive renewals
   - Proper accumulation of rollover credits
   - Correct balance after multiple renewals

5. **Edge Cases**
   - Handling of zero remaining credits
   - Handling of credits with no expiration date
   - Idempotency for duplicate invoice processing
