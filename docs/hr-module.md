# HR, attendance, expenses and native payroll

The online **HR** workspace at `/pos#/hr` connects to Frappe HR. Employee,
Attendance, Expense Claim, Salary Structure Assignment, Salary Slip,
Additional Salary and Payroll Entry remain native records. Daily salary uses
**the site's existing Frappe HR payroll rules only**. EsafePOS does not store
its own daily rates, half-day weights, holiday rules or wage ledger.

## Deployment and permissions

1. Install/configure `hrms`, deploy this app update, then run
   `bench --site <site> migrate`. Restart web/workers as required by your
   deployment. The generated POS build is under `esafepos/public/pos/`.
2. In **Settings → Features**, enable **Frappe HR integration**, then enable
   attendance, expense claims, daily salary and commission payroll separately.
   Daily salary requires attendance; commission payroll requires salesperson
   commissions. Disable dependent children before their parent. Existing native
   documents remain intact when features are disabled. HR cannot be enabled
   without the separate HRMS app.
3. Give attendance operators **HR Manager** plus native Attendance create/submit
   permissions. Staff linked to an active Employee can review their own records
   and create their own claims when native read/create permissions permit it.
4. Give salary/commission preparers **Payroll User** and commission approvers
   **Payroll Manager**, plus the appropriate native document permissions.
   Migration creates these roles if missing, without granting native privileges.
   Older HRMS releases may require HR User for native payroll permissions.
   POS manager/System Manager alone do not grant commission approval.
5. Configure Employee joining dates, holiday lists, shifts, attendance/leave,
   Payroll Settings, Salary Structures/Assignments, payroll periods and accounts
   in Frappe HR. The POS company and native employee/company permissions apply
   to every action. Use the native workflow for non-monthly payroll cycles.

The overview displays installed Frappe/ERPNext/HRMS versions and feature states.
Implementation was checked against official HRMS version-16 controller/schema
sources and version-15 native document references. The upstream latest-release
link resolved to [HRMS v16.60.1](https://github.com/frappe/hrms/releases/tag/v16.60.1)
on 2026-11-28; the running site's exact version is shown in the workspace.
Actual installed-version migration and payroll reconciliation remain rollout
checks. Payroll and HR actions require a connection and cannot be queued offline.

## Attendance and expense claims

Select an employee and month in **Attendance**. An HR Manager can record a
Present, Absent, Half Day or Work From Home exception through today, with a
required reason stored in native comments. The action inserts/submits native
Attendance. Existing dates, shifts, leave and amendments must be reviewed in
Frappe HR; the POS never overwrites an attendance day. Native validation can
adjust status to reflect approved leave.

In **Expense claims**, enter date, type, amount and description, then **Save
claim draft**. Open **Attach receipts and submit claim** for native attachments,
submission, approval and reimbursement. The table shows the latest 100 claims,
including approval and reimbursed amounts. Reimbursements are not salary.
Creation retries retain identities and reject reuse for changed details.

## Daily salary: native rules and Salary Slips

1. Open **Daily salary**, select an employee and completed calendar month.
   The screen shows available native Payroll Settings and links to the native
   settings, assignments and Payroll Entry screens.
2. Choose **Preview native salary**. The native Salary Slip controller applies
   Salary Structure/Assignment, working-day basis, holiday/attendance/leave
   handling, component formulas, additional earnings, taxes and deductions.
   EsafePOS displays the calculated payment days, components, gross, deductions
   and net pay. Preview rolls back database side effects from native calculation,
   including when validation fails; it does not save or submit a Salary Slip.
3. Choose **Save native Salary Slip draft**. Native calculation runs again;
   changed calculated values require a refreshed preview. Existing uncancelled
   slips overlapping the month block another draft. Native create permission,
   a durable request identity/hash and a company transaction lock protect retries.
4. Open the saved native Salary Slip to review, approve, submit and pay it using
   Frappe HR's existing workflow. The POS does not submit Salary Slips or make
   salary cash withdrawals. Native payroll rules determine final amounts.

To change daily wages, half-days, paid leave, holidays, overtime, advances or
other deductions, edit the existing native HR/payroll configuration. There is
no separate POS wage-policy editor. Native payroll currency handling is retained.

## Commissions: review and native payroll hand-off

Existing salesperson reporting continues independently of HR. Commission payroll
uses stored ERPNext Sales Team incentives on submitted POS Invoices and
non-consolidated Sales Invoices for the selected company and completed month.
Native incentives reflect eligible net sales, exclusions, rates and shared
contributions. Allocation must total 100%; eligible salespeople need native
Employee links in the same company. Returns reduce the posting month's total;
consolidated invoices are excluded to avoid counting register close twice.

1. In **Commission payroll**, choose the employee/month and an existing native
   commission Earning component. Configure its company account in Frappe HR.
   Use a payable, non-statistical component without flexible benefits or another
   payment-day proration, and avoid an existing base/formula earning for the same
   component in the employee's assigned structure. Salary/company currencies
   must match for this commission adapter.
2. **Preview earnings** shows the invoice/return source links and total without
   posting. **Save payroll period** reserves one company/employee/month/type key
   and records the source snapshot for review.
3. A Payroll Manager with native Additional Salary submit permission chooses
   **Approve period**. Changed invoices, mappings, component or assignment inputs
   invalidate the snapshot. Approved periods can be reopened before posting.
   The first approval freezes that company/month's invoice and employee-link
   source set. Later source changes require reopening unposted approvals or
   reviewing posted earnings/native adjustments; reassignment cannot pay the
   same salesperson's sales again to another Employee.
4. **Post to payroll** requires native Additional Salary create/submit permission,
   rechecks inputs, and inserts/submits one non-recurring Additional Salary with
   the month-end payroll date and a source-period reference. An existing
   uncancelled Salary Slip overlapping that month blocks late earnings.
5. Process Salary Slips, GL and payment through Frappe HR. Posted commission
   periods remain locked even if an earning is later cancelled; use native
   adjustments rather than deleting/reposting the period. Negative commissions,
   later returns for locked periods and alternative incentive bases require a
   reviewed native adjustment. No cash or separate commission ledger is created.

The adapter checks read permission on all commission sources instead of silently
omitting hidden invoices. More than 5,000 source documents or 1,000 active
employees require native HR review. The POS entry uses calendar months; other
payroll cycles and advanced/native workflow configuration stay in Frappe HR.

## Implementation and verification

- `api/hr.py`: native HR entry points, company/employee/role gates, native Salary
  Slip simulation/draft, commission preview/snapshot/approval/Additional Salary.
- `hr_payroll.py`: pure canonical-month, numeric validation, currency rounding
  and stored-commission aggregation; no daily salary calculation.
- `hr_setup.py`: optional native Attendance/Expense Claim/Salary Slip request
  metadata, approval-role setup and commission-record permission/audit hooks.
- **EsafePOS HR Payroll Batch**: source snapshot, unique commission period,
  preparer/approver/poster audit and native Additional Salary reference. It is
  an approval/retry record. Native HR owns employee and salary business records.
- `HRView.vue`, navigation, session capability and Settings switches provide the
  responsive workspace. Screenshots are in [screenshots/hr](screenshots/hr).

Verification: `python -m unittest esafepos.test_hr_payroll`,
`python scripts/test_hr.py`, `cd frontend && node hr-browser-check.mjs`,
`cd frontend && npm run build`. Tests use mocked Frappe I/O or real Vue with
API fixtures; they do not validate a live payroll/GL/payment cycle. Site
migration, actual native controller calculation, approvals/attachments,
Salary Slip/Additional Salary reconciliation and payment require staging acceptance.

Official references: [Salary Slip](https://docs.frappe.io/hr/salary-slip),
[Payroll Settings](https://docs.frappe.io/hr/payroll-settings),
[Attendance](https://docs.frappe.io/hr/attendance),
[Expense Claim](https://docs.frappe.io/hr/expense-claim), and
[Additional Salary](https://docs.frappe.io/hr/additional-salary).
