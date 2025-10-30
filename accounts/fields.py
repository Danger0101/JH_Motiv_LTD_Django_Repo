# accounts/fields.py
import json
from encrypted_model_fields.fields import EncryptedCharField
from django.db import models

class CustomEncryptedJSONField(EncryptedCharField):
    """
    An Encrypted field that automatically converts Python objects 
    to a JSON string before encryption and converts back after decryption.
    """
    
    # 1. Convert Python Object to JSON String before saving/encryption
    def get_prep_value(self, value):
        if value is not None:
            # Ensure it's not already a string (which the parent class expects)
            if not isinstance(value, str):
                return json.dumps(value)
        return super().get_prep_value(value)

    # 2. Convert JSON String back to Python Object after retrieval/decryption
    def from_db_value(self, value, expression, connection):
        value = super().from_db_value(value, expression, connection)
        if value is not None:
            try:
                # The parent class decrypts it to a string; we load the JSON
                return json.loads(value)
            except (TypeError, json.JSONDecodeError):
                # Handle cases where the stored value isn't valid JSON (e.g., legacy data)
                return value 
        return value

    # Tell Django that this field works with dictionaries/JSON
    def value_to_string(self, obj):
        value = self.value_from_object(obj)
        return json.dumps(value)