from api.user.service import gen_alphanumeric
import pytest

@pytest.mark.run(order=9)
def test_gen_alphanumeric_length():
    # Test default length
    result = gen_alphanumeric()
    assert len(result) == 16, "Default length should be 16"

    # Test custom length
    length = 32
    result = gen_alphanumeric(length)
    assert len(result) == length, f"Length should be {length}"


@pytest.mark.run(order=9)
def test_gen_alphanumeric_characters():
    result = gen_alphanumeric()
    assert all(c.isalnum() for c in result), "Result should only contain alphanumeric characters"


@pytest.mark.run(order=9)
def test_gen_alphanumeric_unique():
    num_samples = 100
    samples = {gen_alphanumeric() for _ in range(num_samples)}
    assert len(samples) == num_samples, "Generated strings should be unique"