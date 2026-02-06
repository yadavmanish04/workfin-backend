# serializers.py
from rest_framework import serializers
from .models import HRProfile, Company, CompanyLocation


class CompanyLocationSerializer(serializers.ModelSerializer):
    city_name = serializers.CharField(source='city.name', read_only=True)
    state_name = serializers.CharField(source='state.name', read_only=True)
    country_name = serializers.CharField(source='country.name', read_only=True)

    class Meta:
        model = CompanyLocation
        fields = ['id', 'city', 'state', 'country', 'city_name', 'state_name', 'country_name', 'address', 'is_headquarters']
        read_only_fields = ['id', 'city_name', 'state_name', 'country_name']


class CompanySerializer(serializers.ModelSerializer):
    locations = CompanyLocationSerializer(many=True, read_only=True)
    locations_count = serializers.SerializerMethodField()

    class Meta:
        model = Company
        fields = [
            'id', 'name', 'logo', 'website', 'size',
            'is_verified', 'locations', 'locations_count'
        ]
        read_only_fields = ['id', 'is_verified', 'locations']

    def get_locations_count(self, obj):
        return obj.locations.count()


class CompanySearchSerializer(serializers.ModelSerializer):
    """Lightweight serializer for company search/autocomplete"""
    logo_url = serializers.SerializerMethodField()
    industry = serializers.SerializerMethodField()

    class Meta:
        model = Company
        fields = ['id', 'name', 'logo_url', 'website', 'size', 'is_verified', 'industry']
        read_only_fields = ['id', 'name', 'logo_url', 'website', 'size', 'is_verified', 'industry']

    def get_logo_url(self, obj):
        """Return full URL for company logo"""
        if obj.logo:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.logo.url)
        return None

    def get_industry(self, obj):
        """You can add industry field to Company model later, for now return placeholder"""
        # TODO: Add industry field to Company model
        return "Technology"  # Placeholder


class HRRegistrationSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(write_only=True)
    company_logo = serializers.ImageField(write_only=True, required=False, allow_null=True)
    company_website = serializers.URLField(write_only=True, required=False, allow_blank=True)
    company_size = serializers.ChoiceField(
        write_only=True,
        choices=[
            ('1-10', '1-10 employees'),
            ('11-50', '11-50 employees'),
            ('51-200', '51-200 employees'),
            ('201-1000', '201-1000 employees'),
            ('1000+', '1000+ employees')
        ]
    )

    # Location fields (optional for registration)
    city_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    state_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    country_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    address = serializers.CharField(write_only=True, required=False, allow_blank=True)
    is_headquarters = serializers.BooleanField(write_only=True, required=False, default=True)

    class Meta:
        model = HRProfile
        fields = [
            'full_name', 'designation', 'phone',
            'company_name', 'company_logo', 'company_website', 'company_size',
            'city_id', 'state_id', 'country_id', 'address', 'is_headquarters'
        ]

    def create(self, validated_data):
        from apps.candidates.models import FilterOption
        from rest_framework.exceptions import ValidationError

        user = self.context['request'].user

        # Extract company details
        company_name = validated_data.pop('company_name')
        company_logo = validated_data.pop('company_logo', None)
        company_website = validated_data.pop('company_website', '')
        company_size = validated_data.pop('company_size')

        # Extract location details
        city_id = validated_data.pop('city_id', None)
        state_id = validated_data.pop('state_id', None)
        country_id = validated_data.pop('country_id', None)
        address = validated_data.pop('address', '')
        is_headquarters = validated_data.pop('is_headquarters', True)

        # VALIDATION: Check if same company with same location already exists
        if city_id:
            # Check if company already exists with this exact location
            existing_company = Company.objects.filter(name__iexact=company_name).first()
            if existing_company:
                # Check if this company already has this location
                from .models import CompanyLocation
                duplicate_location = CompanyLocation.objects.filter(
                    company=existing_company,
                    city_id=city_id
                ).exists()

                if duplicate_location:
                    raise ValidationError({
                        'company_name': f'A recruiter from {company_name} in this city is already registered. Please use a different location or contact your company admin.',
                        'city_id': 'This location already exists for this company.'
                    })

        # Create or get company
        company, created = Company.objects.get_or_create(
            name=company_name,
            defaults={
                'logo': company_logo,
                'website': company_website,
                'size': company_size
            }
        )

        # If company already exists and logo is provided, update it
        if not created and company_logo:
            company.logo = company_logo
            company.save()

        # Create company location if location details provided
        if any([city_id, state_id, country_id]):
            from .models import CompanyLocation

            city = FilterOption.objects.filter(id=city_id).first() if city_id else None
            state = FilterOption.objects.filter(id=state_id).first() if state_id else None
            country = FilterOption.objects.filter(id=country_id).first() if country_id else None

            # Check if THIS EXACT location already exists (same city)
            existing_location = CompanyLocation.objects.filter(
                company=company,
                city=city
            ).first()

            if not existing_location:
                # Create new location only if it doesn't exist
                CompanyLocation.objects.create(
                    company=company,
                    city=city,
                    state=state,
                    country=country,
                    address=address,
                    is_headquarters=is_headquarters
                )

        # Create HR Profile
        validated_data['user'] = user
        validated_data['company'] = company
        return super().create(validated_data)

    def update(self, instance, validated_data):
        from apps.candidates.models import FilterOption

        # Extract company details
        company_name = validated_data.pop('company_name', None)
        company_logo = validated_data.pop('company_logo', None)
        company_website = validated_data.pop('company_website', None)
        company_size = validated_data.pop('company_size', None)

        # Extract location details
        city_id = validated_data.pop('city_id', None)
        state_id = validated_data.pop('state_id', None)
        country_id = validated_data.pop('country_id', None)
        address = validated_data.pop('address', None)
        is_headquarters = validated_data.pop('is_headquarters', True)

        # If company details are provided, create or update company
        if company_name:
            # Create or get company
            company, created = Company.objects.get_or_create(
                name=company_name,
                defaults={
                    'logo': company_logo,
                    'website': company_website or '',
                    'size': company_size or '1-10'
                }
            )

            # If company already exists and logo is provided, update it
            if not created and company_logo:
                company.logo = company_logo
                company.save()

            # Update instance company
            instance.company = company

            # Create company location if location details provided
            if any([city_id, state_id, country_id]):
                city = FilterOption.objects.filter(id=city_id).first() if city_id else None
                state = FilterOption.objects.filter(id=state_id).first() if state_id else None
                country = FilterOption.objects.filter(id=country_id).first() if country_id else None

                # Check if THIS EXACT location already exists for this company (same city)
                existing_location = CompanyLocation.objects.filter(
                    company=company,
                    city=city
                ).first()

                if not existing_location:
                    # Create new location only if it doesn't exist
                    CompanyLocation.objects.create(
                        company=company,
                        city=city,
                        state=state,
                        country=country,
                        address=address or '',
                        is_headquarters=is_headquarters
                    )

        # Update HR profile fields
        return super().update(instance, validated_data)


class HRProfileSerializer(serializers.ModelSerializer):
    email = serializers.CharField(source='user.email', read_only=True)
    balance = serializers.SerializerMethodField()
    total_spent = serializers.SerializerMethodField()
    company_details = CompanySerializer(source='company', read_only=True)
    verification_status = serializers.SerializerMethodField()

    # Write fields for company update
    company_name = serializers.CharField(write_only=True, required=False)
    company_logo = serializers.ImageField(write_only=True, required=False, allow_null=True)
    company_website = serializers.URLField(write_only=True, required=False, allow_blank=True)
    company_size = serializers.ChoiceField(
        write_only=True,
        required=False,
        choices=[
            ('1-10', '1-10 employees'),
            ('11-50', '11-50 employees'),
            ('51-200', '51-200 employees'),
            ('201-1000', '201-1000 employees'),
            ('1000+', '1000+ employees')
        ]
    )

    # Location fields (optional for update)
    city_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    state_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    country_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    address = serializers.CharField(write_only=True, required=False, allow_blank=True)
    is_headquarters = serializers.BooleanField(write_only=True, required=False, default=True)

    class Meta:
        model = HRProfile
        fields = [
            'email', 'full_name', 'designation', 'phone',
            'is_verified', 'verification_status',
            'profile_step', 'is_profile_completed',
            'company_details', 'balance', 'total_spent',
            'company_name', 'company_logo', 'company_website', 'company_size',
            'city_id', 'state_id', 'country_id', 'address', 'is_headquarters'
        ]
        read_only_fields = ['email', 'balance', 'total_spent', 'company_details', 'is_verified', 'verification_status', 'profile_step', 'is_profile_completed']

    def get_verification_status(self, obj):
        """
        Returns combined verification status of both HR and Company
        """
        return {
            'hr_verified': obj.is_verified,
            'company_verified': obj.company.is_verified if obj.company else False,
            'both_verified': obj.is_verified and (obj.company.is_verified if obj.company else False)
        }

    def get_balance(self, obj):
        try:
            return obj.wallet.balance
        except:
            return 0

    def get_total_spent(self, obj):
        try:
            return obj.wallet.total_spent
        except:
            return 0

    def update(self, instance, validated_data):
        from apps.candidates.models import FilterOption

        # Extract company-related fields if present
        company_name = validated_data.pop('company_name', None)
        company_logo = validated_data.pop('company_logo', None)
        company_website = validated_data.pop('company_website', None)
        company_size = validated_data.pop('company_size', None)

        # Extract location details
        city_id = validated_data.pop('city_id', None)
        state_id = validated_data.pop('state_id', None)
        country_id = validated_data.pop('country_id', None)
        address = validated_data.pop('address', None)
        is_headquarters = validated_data.pop('is_headquarters', True)

        # Update company details if any company field is provided
        if any([company_name, company_logo, company_website, company_size]):
            if instance.company:
                company = instance.company

                if company_name and company_name != company.name:
                    # Check if new company name already exists
                    existing_company = Company.objects.filter(name=company_name).first()
                    if existing_company:
                        instance.company = existing_company
                        company = existing_company
                    else:
                        company.name = company_name

                if company_logo:
                    company.logo = company_logo
                if company_website is not None:
                    company.website = company_website
                if company_size:
                    company.size = company_size

                company.save()
            else:
                # Create new company if doesn't exist
                company = Company.objects.create(
                    name=company_name or "Unknown Company",
                    logo=company_logo,
                    website=company_website or "",
                    size=company_size or "1-10"
                )
                instance.company = company
                instance.save()

        # Create/Update company location if location details provided
        if any([city_id, state_id, country_id]) and instance.company:
            city = FilterOption.objects.filter(id=city_id).first() if city_id else None
            state = FilterOption.objects.filter(id=state_id).first() if state_id else None
            country = FilterOption.objects.filter(id=country_id).first() if country_id else None

            # Check if THIS EXACT location already exists for this company (same city)
            existing_location = CompanyLocation.objects.filter(
                company=instance.company,
                city=city
            ).first()

            if not existing_location:
                # Create new location only if it doesn't exist
                CompanyLocation.objects.create(
                    company=instance.company,
                    city=city,
                    state=state,
                    country=country,
                    address=address or '',
                    is_headquarters=is_headquarters
                )

        # Update HR profile fields
        return super().update(instance, validated_data)