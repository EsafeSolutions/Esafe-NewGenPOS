# Weerakoon Agro — Chart of Accounts Map

**Source:** ERPNext Chart of Accounts screenshots supplied on 7 November 2026  
**Company:** Weerakoon Agro  
**Currency shown:** LKR  
**Scope:** This map transcribes the visible account tree and balances. Rows that were collapsed in the screenshots are marked as such; their child accounts and account types were not visible.

## Account tree

```text
Weerakoon Agro
├── Application of Funds (Assets)                                  LKR 11,000.00 Dr
│   ├── Current Assets                                               LKR 11,000.00 Dr
│   │   ├── Accounts Receivable                                      LKR      0.00 Cr
│   │   ├── Bank Accounts                                            LKR      0.00 Cr
│   │   ├── Cash In Hand                                             LKR 11,000.00 Dr
│   │   ├── Loans and Advances (Assets)                              LKR      0.00 Cr [collapsed]
│   │   ├── Prepaid Expenses                                         LKR      0.00 Cr
│   │   ├── Securities and Deposits                                  LKR      0.00 Cr
│   │   ├── Short-term Investments                                   LKR      0.00 Cr
│   │   ├── Stock Assets                                             LKR      0.00 Cr [collapsed]
│   │   └── Tax Assets                                               LKR      0.00 Cr [collapsed]
│   ├── Fixed Assets                                                 LKR      0.00 Cr
│   │   ├── Accumulated Depreciation                                 LKR      0.00 Cr
│   │   ├── Buildings                                                LKR      0.00 Cr
│   │   ├── CWIP Account                                             LKR      0.00 Cr
│   │   ├── Capital Equipment                                        LKR      0.00 Cr
│   │   ├── Electronic Equipment                                     LKR      0.00 Cr
│   │   ├── Furniture and Fixtures                                   LKR      0.00 Cr
│   │   ├── Office Equipment                                         LKR      0.00 Cr
│   │   ├── Plants and Machineries                                   LKR      0.00 Cr
│   │   └── Software                                                 LKR      0.00 Cr
│   ├── Investments                                                  LKR      0.00 Cr [collapsed]
│   └── Temporary Accounts                                           LKR      0.00 Cr
│       └── Temporary Opening                                        LKR      0.00 Cr
├── Source of Funds (Liabilities)                                    LKR      0.00 Cr
│   ├── Current Liabilities                                          LKR      0.00 Cr [collapsed]
│   └── Non-Current Liabilities                                      LKR      0.00 Cr [collapsed]
├── Equity                                                           LKR      0.00 Cr
│   ├── Capital Stock                                                LKR      0.00 Cr
│   ├── Dividends Paid                                               LKR      0.00 Cr
│   ├── Opening Balance Equity                                       LKR      0.00 Cr
│   ├── Retained Earnings                                            LKR      0.00 Cr
│   └── Revaluation Surplus                                          LKR      0.00 Cr
├── Income                                                           LKR 11,000.00 Cr
│   ├── Direct Income                                                LKR 11,000.00 Cr
│   │   ├── Sales                                                    LKR 11,000.00 Cr
│   │   └── Service                                                  LKR      0.00 Cr
│   └── Indirect Income                                              LKR      0.00 Cr [collapsed]
└── Expenses                                                         LKR      0.00 Cr
    ├── Direct Expenses                                              LKR      0.00 Cr
    │   └── Stock Expenses                                           LKR      0.00 Cr [collapsed]
    └── Indirect Expenses                                            LKR      0.00 Cr
        ├── Administrative Expenses                                  LKR      0.00 Cr
        ├── Bank Charges                                             LKR      0.00 Cr
        ├── Commission on Sales                                      LKR      0.00 Cr
        ├── Depreciation                                             LKR      0.00 Cr
        ├── Entertainment Expenses                                   LKR      0.00 Cr
        ├── Exchange Gain/Loss                                       LKR      0.00 Cr
        ├── Freight and Forwarding Charges                           LKR      0.00 Cr
        ├── Gain/Loss on Asset Disposal                              LKR      0.00 Cr
        ├── Impairment                                               LKR      0.00 Cr
        ├── Interest Expense                                         LKR      0.00 Cr
        ├── Legal Expenses                                           LKR      0.00 Cr
        ├── Marketing Expenses                                       LKR      0.00 Cr
        ├── Miscellaneous Expenses                                   LKR      0.00 Cr
        ├── Office Maintenance                                       LKR      0.00 Cr
        ├── Office Rent                                              LKR      0.00 Cr
        ├── Postal Expenses                                          LKR      0.00 Cr
        ├── Print and Stationery                                     LKR      0.00 Cr
        ├── Round Off                                                LKR      0.00 Cr
        ├── Salary                                                   LKR      0.00 Cr
        ├── Sales Expenses                                           LKR      0.00 Cr
        ├── Tax Expense                                              LKR      0.00 Cr
        ├── Telephone Expenses                                       LKR      0.00 Cr
        ├── Travel Expenses                                          LKR      0.00 Cr
        ├── Utility Expenses                                         LKR      0.00 Cr
        └── Write Off                                                LKR      0.00 Cr
```

## Visible balance summary

| Root | Balance shown | Notes |
| --- | ---: | --- |
| Application of Funds (Assets) | LKR 11,000.00 Dr | Entire visible balance is under Current Assets → Cash In Hand. |
| Source of Funds (Liabilities) | LKR 0.00 Cr | Current and non-current liability groups were collapsed. |
| Equity | LKR 0.00 Cr | Listed equity accounts show zero. |
| Income | LKR 11,000.00 Cr | Entire visible balance is under Direct Income → Sales. |
| Expenses | LKR 0.00 Cr | Listed visible expense accounts show zero. |

The visible asset and income totals balance at LKR 11,000. This is only a transcription of the screenshot, not a reconciliation or confirmation that the transactions are classified correctly.

## POS setup notes

The tree view does not show account types, account currencies, disabled status, or the Mode of Payment mappings. Those must be checked on the account and payment method forms before use.

| POS purpose | Relevant visible area | What still needs checking |
| --- | --- | --- |
| Cash tender / register opening | Current Assets → Cash In Hand | Confirm this is a ledger account with Account Type **Cash**, currency LKR, and the Cash Mode of Payment for Weerakoon Agro maps to it. |
| Card or bank transfer tender | Current Assets → Bank Accounts | Expand this group and choose the real bank ledger. Confirm Account Type **Bank**, currency LKR, and map each corresponding Mode of Payment to the correct ledger. |
| Customer balances / due sales | Current Assets → Accounts Receivable | Confirm the customer control account is a ledger with Account Type **Receivable**. POS Credit Sale clearing is provisioned by EsafePOS when enabled. |
| Store Credit refunds / redemption | Current Liabilities (collapsed) and current assets | The customer balance belongs in a liability ledger. EsafePOS uses a separate Bank-type clearing ledger for the payment method and journals the movement to the liability. Do not map the Mode of Payment directly to the liability ledger. |
| Sales | Income → Direct Income → Sales | Confirm this is the intended sales income ledger used by the POS Profile / Item Group defaults. |
| Stock and cost of goods sold | Current Assets → Stock Assets; Expenses → Direct Expenses → Stock Expenses | Expand both groups and confirm the stock, COGS, and stock adjustment accounts required by the inventory setup. |
| Taxes | Current Assets → Tax Assets; Expenses → Indirect Expenses → Tax Expense | Expand and inspect tax ledgers and the POS Profile tax template. Actual tax accounts depend on the company’s tax setup. |

## Accounts not visible in the screenshots

- Child ledgers under Current Liabilities, Non-Current Liabilities, Bank Accounts, Loans and Advances, Stock Assets, Tax Assets, Investments, Indirect Income, and Stock Expenses.
- Account Type, Account Currency, Is Group, and Disabled values for every account.
- Weerakoon Agro’s Mode of Payment account rows and the Accounting tab of the **Finished Goods - ammar** POS Profile.
- Any POS-specific accounts auto-created by EsafePOS (for example, Store Credit Clearing and POS Credit Sale Clearing).

Expand those groups and inspect the Mode of Payment / POS Profile forms before using this map to assign posting accounts.
