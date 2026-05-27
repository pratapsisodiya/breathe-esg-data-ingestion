from django.contrib.auth import authenticate
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response


@api_view(["POST"])
@permission_classes([AllowAny])
def login_view(request):
    username = request.data.get("username") or request.data.get("email")
    password = request.data.get("password")
    user = authenticate(username=username, password=password)
    if not user:
        # Try email-based login
        from django.contrib.auth.models import User
        try:
            u = User.objects.get(email=username)
            user = authenticate(username=u.username, password=password)
        except User.DoesNotExist:
            pass
    if not user:
        return Response({"error": "Invalid credentials"}, status=400)

    token, _ = Token.objects.get_or_create(user=user)
    return Response({
        "token": token.key,
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.get_full_name() or user.username,
            "tenant": user.profile.tenant.name,
            "role": user.profile.role,
        },
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout_view(request):
    request.user.auth_token.delete()
    return Response({"detail": "Logged out"})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me_view(request):
    user = request.user
    return Response({
        "id": user.id,
        "email": user.email,
        "name": user.get_full_name() or user.username,
        "tenant": user.profile.tenant.name,
        "role": user.profile.role,
    })
