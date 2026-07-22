import secrets
import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser("A CLI tool for generating camera claim tokens")
    parser.add_argument("-l", "--length", type=int, help="Length of token to generate", default=32)
    args = parser.parse_args()
    print(secrets.token_urlsafe(args.length))