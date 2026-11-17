from app.agent.agent import run_agent


print("LLM File Assistant (type 'quit' to exit)")
print("Default resume directory: resumes\n")


while True:

    user_query = input("You: ").strip()

    if not user_query:
        continue

    if user_query.lower() in {"quit", "exit"}:
        print("Exiting.")
        break

    run_agent(user_query)

    print()