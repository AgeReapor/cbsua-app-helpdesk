# Team and Office Administration

Open **Helpdesk → Agent Configuration → Team** to manage the existing `HD Team` records. The CBSUA app extends each team with an **Assigned Offices** table backed by the `CB Team Office` child DocType.

Add every office the team is authorized to handle. A team can serve multiple offices. A ticket assigned to a team not mapped to its office is rejected by server validation. Agents resolving tickets must belong to the assigned team. System Manager and Administrator retain administrative override.

No team-office relationship is guessed during installation. Configure it explicitly before routing live tickets to an office.
