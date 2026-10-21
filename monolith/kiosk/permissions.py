from rest_framework import permissions

class IsStaffOrReadOnly(permissions.BasePermission):
    """Allow read-only access to everyone, write access to staff only"""
    
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_staff

class IsOwnerOrStaff(permissions.BasePermission):
    """Allow access to owner or staff"""
    
    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        if hasattr(obj, "patient"):
            return obj.patient.id == request.user.id
        return False
