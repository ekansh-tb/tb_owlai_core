# Copyright (c) 2026, TechBirdIt.in and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class OwlAIConversation(Document):
    def before_insert(self):
        # Auto-set owner to current user if not set
        if not self.owner:
            self.owner = frappe.session.user
    
    def validate(self):
        self.message_count = len(self.messages) if self.messages else 0
    
    def has_permission(self, permtype="read", user=None):
        """Custom permission check for sharing_type"""
        user = user or frappe.session.user
        
        # System Manager always has access
        if "System Manager" in frappe.get_roles(user):
            return True
        
        # Owner always has access
        if self.owner == user:
            return True
        
        # Public conversations are readable by all
        if self.sharing_type == "Public" and permtype == "read":
            return True
        
        # Shared conversations: check if user is in shared_with list
        if self.sharing_type == "Shared":
            shared_users = [d.user for d in self.shared_with] if self.shared_with else []
            if user in shared_users:
                return True
        
        return False

    @staticmethod
    def get_permission_query_conditions(user=None):
        """Build SQL conditions for list view filtering"""
        user = user or frappe.session.user
        
        if "System Manager" in frappe.get_roles(user):
            return ""
        
        # Show: own conversations OR public OR shared with me
        conditions = f"""(
            `tabOwlAI Conversation`.owner = {frappe.db.escape(user)}
            OR `tabOwlAI Conversation`.sharing_type = 'Public'
            OR EXISTS (
                SELECT 1 FROM `tabOwlAI Conversation User` cu 
                WHERE cu.parent = `tabOwlAI Conversation`.name 
                AND cu.user = {frappe.db.escape(user)}
            )
        )"""
        return conditions
