from agents import OpenAIChatCompletionsModel
from openai import AsyncOpenAI
from dotenv import load_dotenv
import os

load_dotenv()

# GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# if not GEMINI_API_KEY:
#     raise ValueError("GEMINI_API_KEY environment variable is not set.")

# client = AsyncOpenAI(
#     api_key=GEMINI_API_KEY,
#     base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
# )
# model = OpenAIChatCompletionsModel(openai_client=client, model="gemini-2.0-flash")

OPEN_ROUTER_KEY = os.getenv("OPEN_ROUTER_KEY")
if not OPEN_ROUTER_KEY:
    raise ValueError("OPEN_ROUTER_KEY environment variable is not set.")

client = AsyncOpenAI(api_key=OPEN_ROUTER_KEY, base_url="https://openrouter.ai/api/v1")

model = OpenAIChatCompletionsModel(
    model="deepseek/deepseek-chat-v3-0324:free", openai_client=client
)

# DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
# if not DEEPSEEK_API_KEY:
#     raise ValueError("DEEPSEEK_API_KEY environment variable is not set.")

# client = AsyncOpenAI(
#     api_key=DEEPSEEK_API_KEY,
#     base_url="https://api.deepseek.com",  # Official DeepSeek API
# )

# model = OpenAIChatCompletionsModel(openai_client=client, model="deepseek-reasoner")
