// SPDX-License-Identifier: MIT.
// starknet-foundry-rs: This is a standard ERC20 Token contract.

use starknet::ContractAddress;

#[starknet::interface]
pub trait IERC20<TContractState> {
    // Getters
    fn get_name(self: @TContractState) -> felt252;
    fn get_symbol(self: @TContractState) -> felt252;
    fn get_decimals(self: @TContractState) -> u8;
    fn total_supply(self: @TContractState) -> u256;
    fn balance_of(self: @TContractState, account: ContractAddress) -> u256;
    fn allowance(self: @TContractState, owner: ContractAddress, spender: ContractAddress) -> u256;

    // Core Functions
    fn transfer(ref self: TContractState, recipient: ContractAddress, amount: u256);
    fn approve(ref self: TContractState, spender: ContractAddress, amount: u256);
    fn transfer_from(ref self: TContractState, sender: ContractAddress, recipient: ContractAddress, amount: u256);
}

#[starknet::contract]
pub mod MyToken {
    use core::num::traits::Zero;
    use core::traits::TryInto;
    use starknet::{ContractAddress, get_caller_address};
    use starknet::storage::{Map, StorageMapReadAccess, StorageMapWriteAccess};
    use starknet::storage::{StoragePointerReadAccess, StoragePointerWriteAccess};

    // --- Storage ---
    #[storage]
    struct Storage {
        name: felt252,
        symbol: felt252,
        decimals: u8,
        total_supply: u256,
        balances: Map::<ContractAddress, u256>,
        allowances: Map::<(ContractAddress, ContractAddress), u256>,
    }

    // --- Events ---
    #[event]
    #[derive(Drop, starknet::Event)]
    enum Event {
        Transfer: Transfer,
        Approval: Approval,
    }

    #[derive(Drop, starknet::Event)]
    struct Transfer {
        from: ContractAddress,
        to: ContractAddress,
        value: u256,
    }

    #[derive(Drop, starknet::Event)]
    struct Approval {
        owner: ContractAddress,
        spender: ContractAddress,
        value: u256,
    }

    // --- Constructor ---
    #[constructor]
    fn constructor(
        ref self: ContractState,
        name: felt252,
        symbol: felt252,
        decimals: u8,
        initial_supply: u256,
        recipient: ContractAddress
    ) {
        self.name.write(name);
        self.symbol.write(symbol);
        self.decimals.write(decimals);
        
        // Mint the initial supply to the recipient
        assert(recipient.is_non_zero(), 'Invalid recipient');
        self.balances.write(recipient, initial_supply);
        self.total_supply.write(initial_supply);
        
        // Emit mint event (Transfer from 0 to recipient)
        self.emit(Event::Transfer(Transfer {
            from: 0.try_into().unwrap(),
            to: recipient,
            value: initial_supply
        }));
    }

    // --- External Functions ---
    #[external(v0)]
    fn get_name(self: @ContractState) -> felt252 {
        self.name.read()
    }

    #[external(v0)]
    fn get_symbol(self: @ContractState) -> felt252 {
        self.symbol.read()
    }

    #[external(v0)]
    fn get_decimals(self: @ContractState) -> u8 {
        self.decimals.read()
    }

    #[external(v0)]
    fn total_supply(self: @ContractState) -> u256 {
        self.total_supply.read()
    }

    #[external(v0)]
    fn balance_of(self: @ContractState, account: ContractAddress) -> u256 {
        self.balances.read(account)
    }

    #[external(v0)]
    fn allowance(self: @ContractState, owner: ContractAddress, spender: ContractAddress) -> u256 {
        self.allowances.read((owner, spender))
    }

    /// Transfers `amount` tokens from the caller's balance to `recipient`.
    /// This is the core token transfer logic.
    #[external(v0)]
    fn transfer(ref self: ContractState, recipient: ContractAddress, amount: u256) {
        let sender = get_caller_address();
        self._transfer(sender, recipient, amount);
    }

    /// Allows `spender` to withdraw from your balance multiple times, up to the `amount`.
    #[external(v0)]
    fn approve(ref self: ContractState, spender: ContractAddress, amount: u256) {
        let owner = get_caller_address();
        self.allowances.write((owner, spender), amount);
        self.emit(Event::Approval(Approval { owner, spender, value: amount }));
    }

    /// Transfers `amount` tokens from `sender` to `recipient` using the allowance mechanism.
    #[external(v0)]
    fn transfer_from(
        ref self: ContractState,
        sender: ContractAddress,
        recipient: ContractAddress,
        amount: u256
    ) {
        let caller = get_caller_address();
        let current_allowance = self.allowances.read((sender, caller));
        assert(current_allowance >= amount, 'ERC20: Allowance too low');
        
        // Update allowance
        self.allowances.write((sender, caller), current_allowance - amount);
        
        // Execute transfer
        self._transfer(sender, recipient, amount);
    }

    // --- Internal Logic ---
    #[generate_trait]
    impl InternalImpl of InternalTrait {
        fn _transfer(ref self: ContractState, sender: ContractAddress, recipient: ContractAddress, amount: u256) {
            // Validation
            assert(sender.is_non_zero(), 'ERC20: invalid sender');
            assert(recipient.is_non_zero(), 'ERC20: invalid recipient');
            assert(amount > 0, 'ERC20: amount must be > 0');

            // Balance check (using u256 logic)
            let sender_balance = self.balances.read(sender);
            assert(sender_balance >= amount, 'ERC20: Insufficient balance');

            // State update
            self.balances.write(sender, sender_balance - amount);
            self.balances.write(recipient, self.balances.read(recipient) + amount);

            // Event emission
            self.emit(Event::Transfer(Transfer { from: sender, to: recipient, value: amount }));
        }
    }
}
