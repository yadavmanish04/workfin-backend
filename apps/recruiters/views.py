from rest_framework import status, generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.db.models import Q
from .models import HRProfile, Company
from .serializers import HRRegistrationSerializer, HRProfileSerializer
from apps.candidates.models import Candidate, UnlockHistory, FilterCategory, FilterOption
from apps.candidates.serializers import MaskedCandidateSerializer, FullCandidateSerializer

class HRRegistrationView(generics.CreateAPIView):
    serializer_class = HRRegistrationSerializer
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        if request.user.role != 'hr':
            return Response({
                'error': 'Only HR users can create HR profiles'
            }, status=status.HTTP_403_FORBIDDEN)

        # If profile already exists, update it instead of creating new
        if hasattr(request.user, 'hr_profile'):
            profile = request.user.hr_profile
            serializer = self.get_serializer(profile, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                # Refresh from database to get updated company with locations
                profile.refresh_from_db()
                # Update profile step
                profile.update_profile_step()
                # Return with HRProfileSerializer to get full company details
                response_serializer = HRProfileSerializer(profile, context={'request': request})
                return Response(response_serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Create new profile
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            hr_profile = serializer.save()
            # Refresh from database to get related company with locations
            hr_profile.refresh_from_db()
            # Update profile step
            hr_profile.update_profile_step()
            # Return with HRProfileSerializer to get full company details
            response_serializer = HRProfileSerializer(hr_profile, context={'request': request})
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def hr_profile(request):
    if request.user.role != 'hr':
        return Response({
            'error': 'Only HR users can access this'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        profile = request.user.hr_profile
        serializer = HRProfileSerializer(profile)
        return Response(serializer.data)
    except HRProfile.DoesNotExist:
        return Response({
            'error': 'HR profile not found'
        }, status=status.HTTP_404_NOT_FOUND)

@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_hr_profile(request):
    if request.user.role != 'hr':
        return Response({
            'error': 'Only HR users can access this'
        }, status=status.HTTP_403_FORBIDDEN)

    try:
        profile = request.user.hr_profile
        serializer = HRProfileSerializer(profile, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            # Refresh from database to get latest data
            profile.refresh_from_db()
            # Update profile step
            profile.update_profile_step()
            # Serialize again to get updated profile_step and is_profile_completed
            updated_serializer = HRProfileSerializer(profile, context={'request': request})
            return Response(updated_serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except HRProfile.DoesNotExist:
        return Response({
            'error': 'HR profile not found'
        }, status=status.HTTP_404_NOT_FOUND)

from django.core.paginator import Paginator


@api_view(['GET'])
def get_all_recruiters(request):
    """Get all recruiters/HR profiles - Public endpoint"""

    # No authentication required - anyone can view recruiters list

    # Get pagination parameters
    page = int(request.query_params.get('page', 1))
    page_size = int(request.query_params.get('page_size', 20))

    # Get all HR profiles
    queryset = HRProfile.objects.select_related('user').all()

    # Optional: Filter by verification status
    is_verified = request.query_params.get('is_verified')
    if is_verified is not None:
        queryset = queryset.filter(is_verified=is_verified.lower() == 'true')

    # Apply pagination
    paginator = Paginator(queryset, page_size)
    recruiters_page = paginator.get_page(page)

    # Serialize recruiters
    serializer = HRProfileSerializer(recruiters_page, many=True, context={'request': request})

    return Response({
        'success': True,
        'recruiters': serializer.data,
        'pagination': {
            'current_page': page,
            'page_size': page_size,
            'total_pages': paginator.num_pages,
            'total_count': paginator.count,
            'has_next': recruiters_page.has_next(),
            'has_previous': recruiters_page.has_previous(),
        }
    })


def normalize_slug(value: str) -> str:
    """
    Converts slug to human readable text
    madhya-pradesh -> Madhya Pradesh
    uttar_pradesh  -> Uttar Pradesh
    """
    return (
        value
        .replace('-', ' ')
        .replace('_', ' ')
        .strip()
        .title()
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def filter_candidates(request):
    """Filter candidates API for HR users"""
    
    if request.user.role != 'hr':
        return Response({
            'error': 'Only HR users can access this'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        hr_profile = request.user.hr_profile

        # Check if HR profile is verified
        if not hr_profile.is_verified:
            return Response({
                'error': 'Your HR profile verification is pending. Please wait for admin approval.',
                'verification_status': {
                    'hr_verified': False,
                    'company_verified': hr_profile.company.is_verified if hr_profile.company else False
                }
            }, status=status.HTTP_403_FORBIDDEN)

        # Check if company exists and is verified
        if not hr_profile.company or not hr_profile.company.is_verified:
            return Response({
                'error': 'Company verification pending. Cannot view candidates.',
                'verification_status': {
                    'hr_verified': hr_profile.is_verified,
                    'company_verified': False
                }
            }, status=status.HTTP_403_FORBIDDEN)

    except HRProfile.DoesNotExist:
        return Response({
            'error': 'HR profile not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Get filter parameters
    role = request.query_params.get('role')
    min_experience = request.query_params.get('min_experience')
    max_experience = request.query_params.get('max_experience')
    min_age = request.query_params.get('min_age')
    max_age = request.query_params.get('max_age')
    city = request.query_params.get('city')
    state = request.query_params.get('state')
    country = request.query_params.get('country')
    religion = request.query_params.get('religion')
    skills = request.query_params.get('skills')
    min_ctc = request.query_params.get('min_ctc')
    max_ctc = request.query_params.get('max_ctc')
    show_locked_only = request.query_params.get('show_locked_only', 'false').lower() == 'true'
    
    # Pagination
    page = int(request.query_params.get('page', 1))
    page_size = int(request.query_params.get('page_size', 20))
    
    # Base queryset - Only show actual candidates, not HR/Recruiter profiles
    queryset = Candidate.objects.filter(
        is_active=True,
        user__role='candidate'
    ).select_related(
        'role', 'religion', 'country', 'state', 'city'
    )
    
    # Apply dynamic filters
    if role and role != 'All':
        queryset = queryset.filter(role__name__iexact=role)
        
    if min_experience:
        try:
            queryset = queryset.filter(experience_years__gte=int(min_experience))
        except ValueError:
            pass
            
    if max_experience:
        try:
            queryset = queryset.filter(experience_years__lte=int(max_experience))
        except ValueError:
            pass
            
    if min_age:
        try:
            queryset = queryset.filter(age__gte=int(min_age))
        except ValueError:
            pass
            
    if max_age:
        try:
            queryset = queryset.filter(age__lte=int(max_age))
        except ValueError:
            pass
            
    if city:
        normalized_city = normalize_slug(city)
        queryset = queryset.filter(city__name__iexact=normalized_city)

    if state:
        normalized_state = normalize_slug(state)
        queryset = queryset.filter(state__name__iexact=normalized_state)

    if country:
        normalized_country = normalize_slug(country)
        queryset = queryset.filter(country__name__iexact=normalized_country)

            
    if religion and religion != 'All':
        queryset = queryset.filter(
        religion__name__iexact=normalize_slug(religion)
    )
        
    if skills:
        queryset = queryset.filter(skills__icontains=skills)
        
    if min_ctc:
        try:
            queryset = queryset.filter(expected_ctc__gte=float(min_ctc))
        except (ValueError, TypeError):
            pass
            
    if max_ctc:
        try:
            queryset = queryset.filter(expected_ctc__lte=float(max_ctc))
        except (ValueError, TypeError):
            pass
    
    # Get unlocked candidate IDs
    unlocked_ids = set(UnlockHistory.objects.filter(
        hr_user=request.user.hr_profile
    ).values_list('candidate_id', flat=True))
    
    # Filter to show only locked candidates if requested
    if show_locked_only:
        queryset = queryset.exclude(id__in=unlocked_ids)
    
    # Apply pagination
    paginator = Paginator(queryset, page_size)
    candidates_page = paginator.get_page(page)
    
    # Serialize candidates
    candidates_data = []
    for candidate in candidates_page:
        if candidate.id in unlocked_ids:
            serializer = FullCandidateSerializer(candidate, context={'request': request})
        else:
            serializer = MaskedCandidateSerializer(candidate, context={'request': request})
        candidates_data.append(serializer.data)
    
    return Response({
        'success': True,
        'candidates': candidates_data,
        'pagination': {
            'current_page': page,
            'page_size': page_size,
            'total_pages': paginator.num_pages,
            'total_count': paginator.count,
            'has_next': candidates_page.has_next(),
            'has_previous': candidates_page.has_previous(),
        },
        'filters_applied': {
            'role': role,
            'experience_range': f"{min_experience}-{max_experience}",
            'age_range': f"{min_age}-{max_age}",
            'location': f"{city}, {state}, {country}",
            'religion': religion,
            'skills': skills,
            'ctc_range': f"{min_ctc}-{max_ctc}"
        }
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def get_countries(request):
    """
    Get all countries for dropdown
    Query params:
    - search: search by name (optional)
    """
    try:
        country_category = FilterCategory.objects.get(slug='country')
        countries = FilterOption.objects.filter(
            category=country_category,
            is_active=True
        )

        # Search functionality
        search = request.query_params.get('search', '').strip()
        if search:
            countries = countries.filter(name__icontains=search)

        countries = countries.values('id', 'name', 'slug').order_by('name')

        return Response({
            'success': True,
            'countries': list(countries)
        })
    except FilterCategory.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Country category not found'
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_states(request):
    """
    Get states filtered by country
    Query params:
    - country: country ID (optional - filters states by country)
    - search: search by name (optional)
    """
    try:
        state_category = FilterCategory.objects.get(slug='state')
        states = FilterOption.objects.filter(
            category=state_category,
            is_active=True
        )

        # Filter by country (parent relationship)
        country_id = request.query_params.get('country')
        if country_id:
            states = states.filter(parent_id=country_id)

        # Search functionality
        search = request.query_params.get('search', '').strip()
        if search:
            states = states.filter(name__icontains=search)

        states = states.values('id', 'name', 'slug', 'parent').order_by('name')

        return Response({
            'success': True,
            'states': list(states)
        })
    except FilterCategory.DoesNotExist:
        return Response({
            'success': False,
            'error': 'State category not found'
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_cities(request):
    """
    Get cities filtered by state
    Query params:
    - state: state ID (optional - filters cities by state)
    - search: search by name (optional)
    """
    try:
        city_category = FilterCategory.objects.get(slug='city')
        cities = FilterOption.objects.filter(
            category=city_category,
            is_active=True
        )

        # Filter by state (parent relationship)
        state_id = request.query_params.get('state')
        if state_id:
            cities = cities.filter(parent_id=state_id)

        # Search functionality
        search = request.query_params.get('search', '').strip()
        if search:
            cities = cities.filter(name__icontains=search)

        cities = cities.values('id', 'name', 'slug', 'parent').order_by('name')

        return Response({
            'success': True,
            'cities': list(cities)
        })
    except FilterCategory.DoesNotExist:
        return Response({
            'success': False,
            'error': 'City category not found'
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([AllowAny])
def check_company_location(request):
    """
    Check if company already exists with the given location
    Query params:
    - company_name: Company name (required)
    - city_id: City UUID (required)

    Returns:
    - exists: Boolean indicating if duplicate exists
    - message: User-friendly message
    """
    company_name = request.query_params.get('company_name', '').strip()
    city_id = request.query_params.get('city_id', '').strip()

    if not company_name or not city_id:
        return Response({
            'success': False,
            'error': 'company_name and city_id are required'
        }, status=status.HTTP_400_BAD_REQUEST)

    # Check if company exists
    existing_company = Company.objects.filter(name__iexact=company_name).first()

    if not existing_company:
        return Response({
            'success': True,
            'exists': False,
            'message': 'Company location is available'
        })

    # Check if this company already has this location
    from .models import CompanyLocation
    duplicate_location = CompanyLocation.objects.filter(
        company=existing_company,
        city_id=city_id
    ).exists()

    if duplicate_location:
        return Response({
            'success': True,
            'exists': True,
            'message': f'A recruiter from {company_name} in this city is already registered.',
            'suggestion': 'Please use a different location or contact your company admin.'
        })

    return Response({
        'success': True,
        'exists': False,
        'message': 'Company location is available'
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def search_companies(request):
    """
    Search companies for autocomplete/autosuggest
    Query params:
    - q: search query (required)
    - limit: number of results (optional, default 10)

    Returns:
    - Companies matching search query with logo, name, website, size
    - Ordered by: verified first, then by name
    """
    search_query = request.query_params.get('q', '').strip()
    limit = int(request.query_params.get('limit', 10))

    if not search_query:
        return Response({
            'success': False,
            'error': 'Search query (q) is required'
        }, status=status.HTTP_400_BAD_REQUEST)

    # Search companies by name (case-insensitive partial match)
    companies = Company.objects.filter(
        name__icontains=search_query
    ).order_by(
        '-is_verified',  # Verified companies first
        'name'
    )[:limit]

    # Serialize results
    from .serializers import CompanySearchSerializer
    serializer = CompanySearchSerializer(companies, many=True, context={'request': request})

    return Response({
        'success': True,
        'query': search_query,
        'count': companies.count(),
        'companies': serializer.data
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def search_companies_by_website(request):
    """
    Search companies by website URL for autocomplete
    Query params:
    - q: search query (website URL) (required)
    - limit: number of results (optional, default 10)

    Returns:
    - Companies matching website URL with logo, name, website, size
    - Ordered by: verified first, then by name
    """
    search_query = request.query_params.get('q', '').strip()
    limit = int(request.query_params.get('limit', 10))

    if not search_query:
        return Response({
            'success': False,
            'error': 'Search query (q) is required'
        }, status=status.HTTP_400_BAD_REQUEST)

    # Search companies by website (case-insensitive partial match)
    companies = Company.objects.filter(
        website__icontains=search_query
    ).order_by(
        '-is_verified',  # Verified companies first
        'name'
    )[:limit]

    # Serialize results
    from .serializers import CompanySearchSerializer
    serializer = CompanySearchSerializer(companies, many=True, context={'request': request})

    return Response({
        'success': True,
        'query': search_query,
        'count': companies.count(),
        'companies': serializer.data
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_custom_location(request):
    """
    Add custom city/state/country (requires admin approval)
    Request body:
    {
        "type": "city|state|country",
        "name": "Custom Location Name",
        "parent": "parent-uuid" (required for city/state)
    }
    """
    if request.user.role != 'hr':
        return Response({
            'success': False,
            'error': 'Only HR users can add custom locations'
        }, status=status.HTTP_403_FORBIDDEN)

    location_type = request.data.get('type')
    name = request.data.get('name', '').strip()
    parent_id = request.data.get('parent')

    if not location_type or not name:
        return Response({
            'success': False,
            'error': 'Type and name are required'
        }, status=status.HTTP_400_BAD_REQUEST)

    if location_type not in ['city', 'state', 'country']:
        return Response({
            'success': False,
            'error': 'Invalid type. Must be city, state, or country'
        }, status=status.HTTP_400_BAD_REQUEST)

    # Check if parent is required
    if location_type in ['city', 'state'] and not parent_id:
        return Response({
            'success': False,
            'error': f'Parent is required for {location_type}'
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        # Get category
        category = FilterCategory.objects.get(slug=location_type)

        # Check if already exists (active or inactive)
        existing = FilterOption.objects.filter(
            category=category,
            name__iexact=name
        ).first()

        if existing:
            if existing.is_active:
                return Response({
                    'success': False,
                    'error': f'{location_type.capitalize()} already exists'
                }, status=status.HTTP_400_BAD_REQUEST)
            else:
                return Response({
                    'success': False,
                    'error': f'{location_type.capitalize()} is pending approval',
                    'pending': True
                }, status=status.HTTP_400_BAD_REQUEST)

        # Verify parent exists if provided
        parent = None
        if parent_id:
            parent = FilterOption.objects.filter(id=parent_id).first()
            if not parent:
                return Response({
                    'success': False,
                    'error': 'Invalid parent ID'
                }, status=status.HTTP_400_BAD_REQUEST)

        # Create slug from name
        from django.utils.text import slugify
        slug = slugify(name)

        # Ensure unique slug
        base_slug = slug
        counter = 1
        while FilterOption.objects.filter(category=category, slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1

        # Create custom location (inactive by default - requires approval)
        custom_location = FilterOption.objects.create(
            category=category,
            name=name.title(),
            slug=slug,
            parent=parent,
            is_active=False  # Requires admin approval
        )

        return Response({
            'success': True,
            'message': f'Custom {location_type} submitted for approval',
            'location': {
                'id': str(custom_location.id),
                'name': custom_location.name,
                'slug': custom_location.slug,
                'is_active': custom_location.is_active,
                'status': 'pending_approval'
            }
        }, status=status.HTTP_201_CREATED)

    except FilterCategory.DoesNotExist:
        return Response({
            'success': False,
            'error': f'{location_type.capitalize()} category not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def search_countries(request):
    """
    Search countries for autocomplete/autosuggest
    Query params:
    - q: search query (required)
    - limit: number of results (optional, default 10)

    Returns:
    - Countries matching search query
    - Ordered by name
    """
    search_query = request.query_params.get('q', '').strip()
    limit = int(request.query_params.get('limit', 10))

    if not search_query:
        return Response({
            'success': False,
            'error': 'Search query (q) is required'
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        country_category = FilterCategory.objects.get(slug='country')

        # Search countries by name (case-insensitive partial match)
        countries = FilterOption.objects.filter(
            category=country_category,
            name__icontains=search_query,
            is_active=True
        ).order_by('name')[:limit]

        countries_data = [
            {
                'id': str(country.id),
                'name': country.name,
                'slug': country.slug
            }
            for country in countries
        ]

        return Response({
            'success': True,
            'query': search_query,
            'count': len(countries_data),
            'countries': countries_data
        })

    except FilterCategory.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Country category not found'
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([AllowAny])
def search_states(request):
    """
    Search states for autocomplete/autosuggest
    Query params:
    - q: search query (required)
    - country: country ID (optional - filters states by country)
    - limit: number of results (optional, default 10)

    Returns:
    - States matching search query
    - Ordered by name
    """
    search_query = request.query_params.get('q', '').strip()
    country_id = request.query_params.get('country', '').strip()
    limit = int(request.query_params.get('limit', 10))

    if not search_query:
        return Response({
            'success': False,
            'error': 'Search query (q) is required'
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        state_category = FilterCategory.objects.get(slug='state')

        # Build query
        query_filter = {
            'category': state_category,
            'name__icontains': search_query,
            'is_active': True
        }

        # Filter by country if provided
        if country_id:
            query_filter['parent_id'] = country_id

        # Search states by name (case-insensitive partial match)
        states = FilterOption.objects.filter(**query_filter).order_by('name')[:limit]

        states_data = [
            {
                'id': str(state.id),
                'name': state.name,
                'slug': state.slug,
                'country_id': str(state.parent_id) if state.parent_id else None
            }
            for state in states
        ]

        return Response({
            'success': True,
            'query': search_query,
            'count': len(states_data),
            'states': states_data
        })

    except FilterCategory.DoesNotExist:
        return Response({
            'success': False,
            'error': 'State category not found'
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([AllowAny])
def search_cities(request):
    """
    Search cities for autocomplete/autosuggest
    Query params:
    - q: search query (required)
    - state: state ID (optional - filters cities by state)
    - limit: number of results (optional, default 10)

    Returns:
    - Cities matching search query
    - Ordered by name
    """
    search_query = request.query_params.get('q', '').strip()
    state_id = request.query_params.get('state', '').strip()
    limit = int(request.query_params.get('limit', 10))

    if not search_query:
        return Response({
            'success': False,
            'error': 'Search query (q) is required'
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        city_category = FilterCategory.objects.get(slug='city')

        # Build query
        query_filter = {
            'category': city_category,
            'name__icontains': search_query,
            'is_active': True
        }

        # Filter by state if provided
        if state_id:
            query_filter['parent_id'] = state_id

        # Search cities by name (case-insensitive partial match)
        cities = FilterOption.objects.filter(**query_filter).order_by('name')[:limit]

        cities_data = [
            {
                'id': str(city.id),
                'name': city.name,
                'slug': city.slug,
                'state_id': str(city.parent_id) if city.parent_id else None
            }
            for city in cities
        ]

        return Response({
            'success': True,
            'query': search_query,
            'count': len(cities_data),
            'cities': cities_data
        })

    except FilterCategory.DoesNotExist:
        return Response({
            'success': False,
            'error': 'City category not found'
        }, status=status.HTTP_404_NOT_FOUND)

