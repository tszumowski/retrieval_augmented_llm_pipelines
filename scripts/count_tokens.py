"""
Counts tokens in jsonlines file and prints the total number of tokens and the total
cost to embed the document store.
"""
import argparse
import jsonlines
import os
import pandas as pd
import sys
from tqdm import tqdm
from typing import Any, Dict, List, Sequence

sys.path.append(
    os.path.join(os.path.dirname(__file__), "../cloud_functions/embedding-indexer")
)

from tokenization import tiktoken_len


def count_tokens(data: Sequence[Dict[str, Any]]) -> List[int]:
    """
    Counts tokens in jsonlines file "text" fields

    Args:
        data): The data to count tokens in.
            Each line should be a json object with a "text" field.

    Returns:
        token_cnts: The number of tokens in each document.
    """

    # Tokenize the cleaned data and print the total number of tokens
    n_tokens = 0
    token_cnts = list()
    for d in tqdm(data):
        cur_text = d["text"]
        cur_token_len = tiktoken_len(cur_text)
        n_tokens += cur_token_len
        token_cnts.append(cur_token_len)

    return token_cnts


if __name__ == "__main__":
    # arg parse jsonlines file
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input_file",
        type=str,
        required=True,
        help="The jsonlines file to count tokens in. Each line should be a json object with a 'text' field.",
    )
    parser.add_argument(
        "--token_cost",
        type=float,
        required=False,
        default=0.0004 / 1000,
        help="The cost per token to embed a document. Defaults to 0.0004 cents per 1000 tokens which is for gpt-3.5-turbo",
    )
    args = parser.parse_args()

    input_file = args.input_file
    token_cost = args.token_cost

    # read in the jsonlines file into data
    data = list()
    print(f"Reading in data from file: {input_file} ...")
    with jsonlines.open(input_file) as reader:
        for obj in reader:
            data.append(obj)
    print(f"Read in {len(data)} records from file.")

    # Tokenize the data and print the total number of tokens
    token_cnts = count_tokens(data)

    # Sum to get total number of tokens
    n_tokens = sum(token_cnts)

    print(f"Total number of tokens in document store: {n_tokens}")
    print(f"Total cost to embed document store: ${n_tokens * token_cost:.2f}")

    # Get some stats on the tokens too
    token_cnts_df = pd.DataFrame(token_cnts, columns=["token_cnt"])
    print(f"Token count stats:")
    print(token_cnts_df.describe())
