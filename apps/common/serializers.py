from collections.abc import Mapping

from rest_framework import serializers


class StrictFieldsSerializer(serializers.Serializer):
    """Reject unexpected input instead of silently ignoring it."""

    def to_internal_value(self, data):
        if isinstance(data, Mapping):
            unknown_fields = set(data) - set(self.fields)
            if unknown_fields:
                raise serializers.ValidationError(
                    {field: ["Unknown field."] for field in sorted(unknown_fields)}
                )
        return super().to_internal_value(data)

