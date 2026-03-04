# Copyright (c) 2024, TechBirdIt.in and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class OwlAICrew(Document):
    def kickoff(self):
        """
        CrewAI integration has been removed as part of the enterprise refactor.
        OwlAI now uses a native Frappe engine (engine/core.py) with zero
        third-party AI framework dependencies.
        """
        frappe.throw(
            "CrewAI integration has been removed. "
            "Use the OwlAI native engine via the chat API instead.",
            title="Feature Removed",
        )
