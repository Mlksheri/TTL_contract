import argparse
import asyncio
import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from tabulate import tabulate


PROJECT_ROOT = Path(__file__).resolve().parent
TARGET_DIR = PROJECT_ROOT / "target" / "dev"
ARTIFACTS_FILE = TARGET_DIR / "ttl_contract.starknet_artifacts.json"

TOKEN_NAME = os.getenv("TOKEN_NAME", "MyDashboardToken")
TOKEN_SYMBOL = os.getenv("TOKEN_SYMBOL", "MDT")
DECIMALS = int(os.getenv("TOKEN_DECIMALS", "18"))
INITIAL_SUPPLY = int(os.getenv("TOKEN_INITIAL_SUPPLY", str(10000 * 10**DECIMALS)))


def parse_int(value: str) -> int:
    return int(value, 0)


def env_required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise SystemExit(f"Missing {name}. Set it with: $env:{name}='...'")
    return value


def friendly_network_error(exc: Exception) -> SystemExit:
    rpc_url = os.getenv("STARKNET_RPC_URL", "http://localhost:5050")
    return SystemExit(
        "Could not connect to the Starknet RPC endpoint.\n"
        f"Current STARKNET_RPC_URL: {rpc_url}\n"
        "If this is localhost:5050, start a local Starknet devnet first. "
        "For Sepolia, set STARKNET_RPC_URL to your provider's Sepolia RPC URL."
    )


def format_units(raw_amount: int, decimals: int = DECIMALS) -> str:
    whole = raw_amount // 10**decimals
    fraction = raw_amount % 10**decimals
    if fraction == 0:
        return str(whole)
    return f"{whole}.{str(fraction).zfill(decimals).rstrip('0')}"


def parse_units(amount: str, decimals: int = DECIMALS) -> int:
    if "." not in amount:
        return int(amount) * 10**decimals

    whole, fraction = amount.split(".", 1)
    if len(fraction) > decimals:
        raise ValueError(f"Amount has more than {decimals} decimal places.")
    return int(whole or "0") * 10**decimals + int(fraction.ljust(decimals, "0"))


def find_scarb() -> str:
    scarb = shutil.which("scarb")
    if scarb:
        return scarb

    local_scarb = (
        Path(os.getenv("LOCALAPPDATA", ""))
        / "Programs"
        / "scarb"
        / "scarb-v2.18.0-x86_64-pc-windows-msvc"
        / "bin"
        / "scarb.exe"
    )
    if local_scarb.exists():
        return str(local_scarb)

    raise SystemExit("Scarb was not found. Install Scarb or open a new PowerShell window.")


def build_contract() -> None:
    subprocess.run([find_scarb(), "build"], cwd=PROJECT_ROOT, check=True)


def artifact_paths() -> tuple[Path, Path]:
    if not ARTIFACTS_FILE.exists():
        build_contract()

    artifacts = json.loads(ARTIFACTS_FILE.read_text())
    token = next(item for item in artifacts["contracts"] if item["contract_name"] == "MyToken")
    sierra = TARGET_DIR / token["artifacts"]["sierra"]
    casm = TARGET_DIR / token["artifacts"]["casm"]

    if not sierra.exists() or not casm.exists():
        build_contract()

    return sierra, casm


def starknet_imports():
    mingw_bin = Path("C:/msys64/mingw64/bin")
    if mingw_bin.exists():
        os.environ["PATH"] = f"{mingw_bin};{os.environ['PATH']}"
        os.add_dll_directory(str(mingw_bin))

    try:
        from starknet_py.cairo.felt import decode_shortstring, encode_shortstring
        from starknet_py.contract import Contract
        from starknet_py.net.account.account import Account
        from starknet_py.net.full_node_client import FullNodeClient
        from starknet_py.net.models import StarknetChainId
        from starknet_py.net.signer.stark_curve_signer import KeyPair
    except Exception as exc:
        raise SystemExit(
            "starknet-py could not load in this Python environment.\n"
            "For live deploy/transfer, use Python 3.12 or 3.13, recreate .venv, then reinstall requirements.txt.\n"
            f"Original error: {exc}"
        ) from exc

    return {
        "Account": Account,
        "Contract": Contract,
        "FullNodeClient": FullNodeClient,
        "KeyPair": KeyPair,
        "StarknetChainId": StarknetChainId,
        "decode_shortstring": decode_shortstring,
        "encode_shortstring": encode_shortstring,
    }


def create_account():
    imports = starknet_imports()
    network = os.getenv("STARKNET_NETWORK", "local").lower()
    chain = (
        imports["StarknetChainId"].MAINNET
        if network == "mainnet"
        else imports["StarknetChainId"].SEPOLIA
    )

    return imports["Account"](
        client=imports["FullNodeClient"](node_url=env_required("STARKNET_RPC_URL")),
        address=parse_int(env_required("STARKNET_ACCOUNT_ADDRESS")),
        key_pair=imports["KeyPair"].from_private_key(parse_int(env_required("STARKNET_PRIVATE_KEY"))),
        chain=chain,
    )


async def deploy_live():
    imports = starknet_imports()
    account = create_account()
    sierra, casm = artifact_paths()

    try:
        print("Declaring ERC20 contract class...")
        declare_result = await imports["Contract"].declare_v3(
            account=account,
            compiled_contract=sierra.read_text(),
            compiled_contract_casm=casm.read_text(),
            auto_estimate=True,
        )
        await declare_result.wait_for_acceptance()

        print(f"Class hash: {hex(declare_result.class_hash)}")
        print("Deploying ERC20 contract...")

        deploy_result = await declare_result.deploy_v3(
            constructor_args={
                "name": imports["encode_shortstring"](TOKEN_NAME),
                "symbol": imports["encode_shortstring"](TOKEN_SYMBOL),
                "decimals": DECIMALS,
                "initial_supply": INITIAL_SUPPLY,
                "recipient": account.address,
            },
            auto_estimate=True,
        )
        await deploy_result.wait_for_acceptance()
        print(f"Token address: {hex(deploy_result.deployed_contract.address)}")
    except OSError as exc:
        raise friendly_network_error(exc) from exc


def first_field(result, name: str):
    if hasattr(result, name):
        return getattr(result, name)
    if isinstance(result, tuple):
        return result[0]
    return result


def as_int(value) -> int:
    if isinstance(value, int):
        return value
    if hasattr(value, "low") and hasattr(value, "high"):
        return value.low + (value.high << 128)
    if isinstance(value, tuple) and len(value) == 2:
        return value[0] + (value[1] << 128)
    return int(value)


async def connect_live(address: str | None):
    imports = starknet_imports()
    account = create_account()
    token_address = parse_int(address or env_required("TOKEN_ADDRESS"))
    contract = await imports["Contract"].from_address(address=token_address, provider=account)
    return imports, account, contract


async def dashboard_live(address: str | None):
    imports, account, contract = await connect_live(address)

    name = first_field(await contract.functions["get_name"].call(), "get_name")
    symbol = first_field(await contract.functions["get_symbol"].call(), "get_symbol")
    decimals = first_field(await contract.functions["get_decimals"].call(), "get_decimals")
    total_supply = as_int(first_field(await contract.functions["total_supply"].call(), "total_supply"))
    balance = as_int(first_field(await contract.functions["balance_of"].call(account.address), "balance_of"))

    decoded_symbol = imports["decode_shortstring"](symbol)
    rows = [
        ["Contract", hex(contract.address)],
        ["Token", f"{imports['decode_shortstring'](name)} ({decoded_symbol})"],
        ["Total supply", f"{format_units(total_supply, decimals)} {decoded_symbol}"],
        ["Your balance", f"{format_units(balance, decimals)} {decoded_symbol}"],
        ["Network", os.getenv("STARKNET_NETWORK", "local")],
        ["Updated", datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
    ]
    print(tabulate(rows, headers=["Metric", "Value"], tablefmt="grid"))


async def transfer_live(address: str | None, recipient: str, amount: str):
    imports, _, contract = await connect_live(address)
    decimals = first_field(await contract.functions["get_decimals"].call(), "get_decimals")
    symbol = imports["decode_shortstring"](
        first_field(await contract.functions["get_symbol"].call(), "get_symbol")
    )
    raw_amount = parse_units(amount, decimals)

    print(f"Sending {amount} {symbol} to {recipient}...")
    tx = await contract.functions["transfer"].invoke_v3(
        recipient=parse_int(recipient),
        amount=raw_amount,
        auto_estimate=True,
    )
    await tx.wait_for_acceptance()
    tx_hash = getattr(tx, "hash", None)
    print(f"Transfer accepted: {hex(tx_hash) if tx_hash else 'accepted'}")


@dataclass
class DemoToken:
    name: str = TOKEN_NAME
    symbol: str = TOKEN_SYMBOL
    decimals: int = DECIMALS
    owner: str = "0x111"
    recipient: str = "0x222"
    total_supply: int = INITIAL_SUPPLY

    def __post_init__(self):
        self.balances = {self.owner: self.total_supply, self.recipient: 0}

    def transfer(self, sender: str, recipient: str, raw_amount: int) -> str:
        if raw_amount <= 0:
            raise ValueError("Amount must be greater than zero.")
        if self.balances.get(sender, 0) < raw_amount:
            raise ValueError("Insufficient balance.")

        self.balances[sender] -= raw_amount
        self.balances[recipient] = self.balances.get(recipient, 0) + raw_amount
        return "0xdemo_transfer_hash"


def print_demo_dashboard(token: DemoToken):
    rows = [
        ["Mode", "Local demo"],
        ["Token", f"{token.name} ({token.symbol})"],
        ["Total supply", f"{format_units(token.total_supply)} {token.symbol}"],
        ["Owner", token.owner],
        ["Owner balance", f"{format_units(token.balances[token.owner])} {token.symbol}"],
        ["Recipient", token.recipient],
        ["Recipient balance", f"{format_units(token.balances[token.recipient])} {token.symbol}"],
        ["Updated", datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
    ]
    print(tabulate(rows, headers=["Metric", "Value"], tablefmt="grid"))


def demo_dashboard(amount: str):
    token = DemoToken()
    print_demo_dashboard(token)
    raw_amount = parse_units(amount)
    tx_hash = token.transfer(token.owner, token.recipient, raw_amount)
    print(f"\nTransfer executed: {amount} {token.symbol}")
    print(f"Demo tx hash: {tx_hash}\n")
    print_demo_dashboard(token)


async def main():
    parser = argparse.ArgumentParser(description="Cairo ERC20 token transfer dashboard.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("build", help="Compile the Cairo contract with Scarb.")
    sub.add_parser("deploy", help="Declare and deploy the token to Starknet.")

    demo = sub.add_parser("demo", help="Execute a local dashboard transfer demo.")
    demo.add_argument("--amount", default="25", help="Token amount to transfer in demo mode.")

    dashboard = sub.add_parser("dashboard", help="Show a live deployed token dashboard.")
    dashboard.add_argument("--address", help="Token contract address. Defaults to TOKEN_ADDRESS.")

    transfer = sub.add_parser("transfer", help="Transfer tokens on Starknet.")
    transfer.add_argument("recipient", help="Recipient address.")
    transfer.add_argument("amount", help="Token amount, e.g. 12.5")
    transfer.add_argument("--address", help="Token contract address. Defaults to TOKEN_ADDRESS.")

    args = parser.parse_args()

    if args.command == "build":
        build_contract()
    elif args.command == "deploy":
        await deploy_live()
    elif args.command == "demo":
        demo_dashboard(args.amount)
    elif args.command == "dashboard":
        await dashboard_live(args.address)
    elif args.command == "transfer":
        await transfer_live(args.address, args.recipient, args.amount)


if __name__ == "__main__":
    asyncio.run(main())
