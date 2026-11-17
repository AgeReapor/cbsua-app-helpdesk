# Office Request Type Administration

Open **Helpdesk → CBSUA Office Routing → Office Request Types** to create and maintain `CB Office Request Type` records.

Each record belongs to exactly one `CB Office`. Request type codes are globally unique, allowing the label `Inquiry` to be configured independently for each office.

Fresh installation creates Tech Support and Inquiry for ICT, and Inquiry for Registrar, Admissions, and Cashier. Add or disable request types independently without code changes. The ticket form loads only enabled request types for the selected office. Server validation rejects a type belonging to another office.
