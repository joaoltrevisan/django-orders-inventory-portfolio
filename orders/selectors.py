from accounts.models import Customer, User

from .models import Order


def orders_visible_to(actor):
    """Scope before collection or object lookup; object permissions do not filter lists."""
    queryset = Order.objects.all()
    if not isinstance(actor, User) or not actor.pk:
        return queryset.none()
    current = User.objects.filter(pk=actor.pk, is_active=True).first()
    if current is None:
        return queryset.none()
    if current.is_staff:
        return queryset
    if Customer.objects.filter(user_id=current.pk).exists():
        return queryset.filter(customer__user_id=current.pk)
    return queryset.none()
