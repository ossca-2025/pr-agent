def main():
    user = get_user()
    data = fetch_data(user)
    result = process(data)
    save_result(result)


def get_user():
    print("Getting user info...")
    return "user_123"


def fetch_data(user_id):
    print(f"Fetching data for {user_id}...")
    return {"value": 42}


def process(data):
    print("Processing data...")
    return data["value"] * 2


def save_result(result):
    print(f"Saving result: {result}")
