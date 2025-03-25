import json

from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from rest_framework import generics, viewsets, status
from rest_framework.decorators import action, api_view
from rest_framework.exceptions import ValidationError
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from booket.models import ProviderServer, Client, logger, Provider, ProviderClient, AppointmentService, Appointment, \
    Service, OTPVerification
from .serializers import ProviderServerSerializer, ClientSerializer
from rest_framework.response import Response
from datetime import datetime
from django.utils import timezone

from ..utils import valid_signature, mask_email, mask_phone_number


class ProviderServerDetailView(generics.RetrieveAPIView):
    throttle_classes = [AnonRateThrottle]
    serializer_class = ProviderServerSerializer

    def get(self, request, p_server_id):
        if not valid_signature(request):
            return Response({"error": "Invalid request headers"}, status=400)
        try:
            provider_server = ProviderServer.objects.get(id=p_server_id)
            serializer = self.serializer_class(provider_server)
            return Response(serializer.data)
        except ProviderServer.DoesNotExist:
            return Response({"error": "Provider Server not found"}, status=404)


class AvailableTimeSlotsView(APIView):
    throttle_classes = [AnonRateThrottle]

    def get(self, request, p_server_id):
        if not valid_signature(request):
            return Response({"error": "Invalid request headers"}, status=400)
        provider_server = ProviderServer.objects.filter(id=p_server_id).first()
        if not provider_server:
            return Response({"error": "Provider Server not found"}, status=404)
        start_date = request.GET.get('start_date')
        if (
            start_date
            and
            datetime.strptime(str(start_date), "%Y-%m-%d").date() < datetime.today().date()
        ):
            start_date = datetime.today().date()
        serializer = ProviderServerSerializer()
        available_slots = serializer._calculate_available_slots(provider_server, start_date)

        return Response({"available_slots": available_slots})


class ClientViewSet(viewsets.ReadOnlyModelViewSet):
    throttle_classes = [AnonRateThrottle]
    queryset = Client.objects.all()
    serializer_class = ClientSerializer

    @action(detail=False, methods=["get"])
    def search(self, request):
        if not valid_signature(request):
            return Response({"error": "Invalid request headers"}, status=400)
        email = request.query_params.get("email")
        phone_number = request.query_params.get("phone_number")

        if email:
            client = get_object_or_404(Client, email=email)
        elif phone_number:
            client = get_object_or_404(Client, phone_number=phone_number)
        else:
            return Response({"error": "Provide either email or phone_number"}, status=400)

        serializer = self.get_serializer(client)
        return Response(serializer.data)


def get_client_data(request):
    """Get client data to check if it exists."""
    response = {}
    if request.method == "GET":
        if not valid_signature(request):
            response["success"] = False
            response["message"] = "Invalid signature."
            return JsonResponse(response, status=400)
        phone_number = request.GET.get("phone_number")
        email = request.GET.get("email")
        try:
            if phone_number:
                client = Client.objects.get(phone_number=phone_number)
            elif email:
                client = Client.objects.get(email=email)
            else:
                raise ValidationError("Not a valid phone or email")
            response["success"] = True
            response["client_id"] = client.id
            response["client_email"] = client.email
            response["client_phone"] = client.phone_number
            response["client_full_name"] = client.full_name
            response["client_sex"] = client.sex
            response["client_dob"] = client.date_of_birth
            return JsonResponse(response)
        except Client.DoesNotExist:
            response["success"] = False
            response["error"] = "Client does not exist"
        except Exception as e:
            response["success"] = False
            response["error"] = str(e)
        return JsonResponse(response, status=404)


@api_view(["POST"])
def create_appointment_send_otp(request):
    """
    Creates an appointment, handles client creation/update,
    manages ProviderClient relationship, and sends OTP.
    """
    if not valid_signature(request):
        return Response({"error": "Invalid request headers"}, status=status.HTTP_400_BAD_REQUEST)

    if request.method != "POST":
        return Response({"error": "Method not allowed"}, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    try:
        with transaction.atomic():  # Use atomic transaction for data consistency
            appointment_data = request.data  # Access data directly from request.data
            client_data = appointment_data["client"]

            # Client creation/update
            if client_data.get("client_id"):
                client = get_object_or_404(Client, id=client_data["client_id"], is_active=True)
                client.full_name = client_data.get("full_name")
                client.phone_number = client_data.get("phone_number")
                client.email = client_data.get("email")
                client.sex = client_data.get("sex")
                client.date_of_birth = datetime.strptime(client_data.get("dob"), "%Y-%m-%d").date()
                client.language_code = appointment_data.get("language_code")
                client.save()
            else:
                client = Client.objects.create(
                    full_name=client_data["full_name"],
                    phone_number=client_data["phone_number"],
                    email=client_data["email"],
                    sex=client_data["sex"],
                    date_of_birth=datetime.strptime(client_data["dob"], "%Y-%m-%d").date(),
                )

            # ProviderClient relationship
            provider = get_object_or_404(Provider, id=appointment_data["provider_id"])
            ProviderClient.objects.get_or_create(provider=provider, client=client)

            # Appointment creation
            server = get_object_or_404(ProviderServer, id=appointment_data["server_id"]).server
            start_datetime = timezone.make_aware(
                datetime.strptime(
                    f"{appointment_data['date']} {appointment_data['time']}", "%Y-%m-%d %H:%M"
                )
            )
            total_duration = sum(service["duration"] for service in appointment_data["services"])
            end_datetime = start_datetime + timezone.timedelta(minutes=total_duration)

            appointment = Appointment.objects.create(
                client=client,
                server=server,
                start_datetime=start_datetime,
                end_datetime=end_datetime,
                status="NEW",
                comment=appointment_data.get("comments"),
            )

            # AppointmentService creation
            for ap_service in appointment_data["services"]:
                service = get_object_or_404(Service, id=ap_service["service_id"])
                AppointmentService.objects.create(appointment=appointment, service=service)

            # OTP creation and sending
            otp = OTPVerification.objects.create(
                appointment=appointment,
                phone_number=client.phone_number,
                email=client.email,
                verification_method=client_data["confirmation_method"]
            )
            otp.send_otp()
            logger.info(f"OTP code: {otp.otp_code}")  # Log OTP code for debugging
            masked_email = mask_email(client.email)
            masked_phone_number = mask_phone_number(client.phone_number)
            response_data = {
                "success": True,
                "message": "Appointment created successfully",
                "confirmation_method": client_data["confirmation_method"],
                "masked_email": masked_email,
                "masked_phone_number": masked_phone_number,
                "otp_id": otp.id,
            }
            return Response(response_data, status=status.HTTP_201_CREATED)

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON data: {e}")
        return Response({"success": False, "message": "Invalid JSON data"}, status=status.HTTP_400_BAD_REQUEST)
    except KeyError as e:
        logger.error(f"Missing key in request data: {e}")
        return Response({"success": False, "message": f"Missing required field: {e}"}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Error on create_appointment_send_otp: {e}", exc_info=True)
        return Response({"success": False, "message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["POST"])
def confirmOTP(request):
    if not valid_signature(request):
        return Response({"error": "Invalid request headers"}, status=status.HTTP_400_BAD_REQUEST)

    if request.method != "POST":
        return Response({"error": "Method not allowed"}, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    try:
        opt_id = request.data.get("otp_id")
        otp_code = request.data.get("otp_code")
        otp = OTPVerification.objects.get(id=opt_id, otp_code=otp_code, is_verified=False)
        if otp:
            otp.is_verified = True
            appointment = otp.appointment
            appointment.status = "ACCEPTED"
            appointment.save()
            otp.save()
            return Response({"success": True, "message": "OTP verified successfully"}, status=status.HTTP_200_OK)
        else:
            return Response({"success": False, "message": "Invalid OTP"}, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        logger.error(f"Error on confirmOTP: {e}", exc_info=True)
        return Response({"success": False, "message": "OTP confirmation failed"}, status=status.HTTP_400_BAD_REQUEST)
