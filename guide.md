# Starknet Token Transfer Project Guide

This project contains a Cairo ERC20-style token contract and a Python dashboard for building, deploying, viewing balances, and transferring tokens.

## Project Files

| File | Purpose |
| --- | --- |
| `erc20.cairo` | Main Cairo contract code for the token. |
| `src/lib.cairo` | Scarb build source for the same contract. |
| `Scarb.toml` | Scarb package and Starknet contract build configuration. |
| `token_dashboard.py` | Python CLI dashboard for build, deploy, dashboard, transfer, and local demo commands. |
| `requirements.txt` | Python dependencies for the dashboard. |
| `target/dev/*.json` | Generated contract artifacts after `scarb build`. |


##Main storage fields:

```cairo
name: felt252,
symbol: felt252,
decimals: u8,
total_supply: u256,
balances: Map::<ContractAddress, u256>,
allowances: Map::<(ContractAddress, ContractAddress), u256>,
```

Main public functions:

| Function | Description |
| --- | --- |
| `get_name` | Returns the token name. |
| `get_symbol` | Returns the token symbol. |
| `get_decimals` | Returns token decimals. |
| `total_supply` | Returns total supply. |
| `balance_of` | Returns the balance of an address. |
| `allowance` | Returns approved allowance from owner to spender. |
| `transfer` | Transfers tokens from caller to recipient. |
| `approve` | Approves another address to spend tokens. |
| `transfer_from` | Transfers tokens using an allowance. |

The constructor mints the initial supply to the recipient address passed during deployment.

## Run Scarb :

```powershell
scarb build
```


```text
target/dev/ttl_contract_MyToken.contract_class.json
target/dev/ttl_contract_MyToken.compiled_contract_class.json
target/dev/ttl_contract.starknet_artifacts.json
```

## Python Dependencies

Install dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

The dashboard uses:

```text
starknet-py
tabulate
```

Important: `starknet-devnet` from PyPI does not support Python 3.14. The local demo command does not require devnet.

## Expected behavior:

```text
Owner balance:     10000 MDT -> 9975 MDT
Recipient balance: 0 MDT     -> 25 MDT
```

Use this to prove the dashboard and transfer math are working before live deployment.

## Live Deployment Configuration

Before deploying, set environment variables in PowerShell:

```powershell
$env:STARKNET_RPC_URL="YOUR_RPC_URL"
$env:STARKNET_ACCOUNT_ADDRESS="0xYOUR_ACCOUNT_ADDRESS"
$env:STARKNET_PRIVATE_KEY="0xYOUR_PRIVATE_KEY"
$env:STARKNET_NETWORK="sepolia"
```

For Sepolia, the RPC URL usually comes from Alchemy, Infura, Blast, Lava, or another Starknet RPC provider.

Example shape:

```powershell
$env:STARKNET_RPC_URL="https://starknet-sepolia.g.alchemy.com/starknet/version/rpc/v0_8/YOUR_API_KEY"
```

Never paste your private key directly into `token_dashboard.py`. Keep it in the environment variable.


The deploy process:

1. Loads Sierra and CASM artifacts from `target/dev`.
2. Declares the contract class.
3. Deploys the token with constructor values.
4. Mints initial supply to `STARKNET_ACCOUNT_ADDRESS`.
5. Prints the deployed token address.

The dashboard prints:

| Metric | Meaning |
| --- | --- |
| Contract | Deployed token contract address. |
| Token | Token name and symbol. |
| Total supply | Total token supply. |
| Your balance | Balance of `STARKNET_ACCOUNT_ADDRESS`. |
| Network | Current network label. |
| Updated | Local timestamp. |

The script:

1. Reads token decimals and symbol.
2. Converts the human amount to raw token units.
3. Calls the contract `transfer` function.
4. Waits for transaction acceptance.
5. Prints the transaction hash.

