def supplier_context(request):
    if request.user.is_authenticated and hasattr(request.user, 'supplier'):
        return {'supplier': request.user.supplier}
    return {}


def client_context(request):
    if request.user.is_authenticated and hasattr(request.user, 'client'):
        return {'client': request.user.client}
    return {}
