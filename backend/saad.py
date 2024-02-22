import asyncio

from redis.asyncio import Redis


async def main():
    i = 1
    while True:
        print(f"Iteration: {i}")
        async with Redis() as redis:
            await redis.json().get("applications:master:api:api/user/user_profile")
            # print(result)
        


if __name__ == "__main__":
    # print("EEEEE")
    asyncio.run(main())
