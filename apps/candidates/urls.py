from django.urls import path
from .views import *
from .views import save_candidate_step, get_candidate_availability, update_candidate_availability


urlpatterns = [
    path('register/', CandidateRegistrationView.as_view(), name='candidate-register'),
    path('profile/', get_candidate_profile, name='candidate-profile'),
    path('profile/update/', update_candidate_profile, name='candidate-profile-update'),
    path('availability/', get_candidate_availability, name='candidate-availability'),
    path('availability/update/', update_candidate_availability, name='update-candidate-availability'),
    path('list/', CandidateListView.as_view(), name='candidate-list'),
    path('<uuid:candidate_id>/unlock/', unlock_candidate, name='unlock-candidate'),
    path('unlocked/', get_unlocked_candidates, name='unlocked-candidates'),
    path('filter-options/', get_filter_options, name='candidate-filter-options'),
    path('filter-categories/', get_filter_categories, name='filter-categories'),
    path('<uuid:candidate_id>/note/', add_candidate_note, name='add-candidate-note'),
    path('<uuid:candidate_id>/note/<uuid:note_id>/', add_candidate_note, name='delete-candidate-note'),
    path('<uuid:candidate_id>/followup/', add_candidate_followup, name='add-candidate-followup'),
    path('<uuid:candidate_id>/followup/<uuid:followup_id>/', add_candidate_followup, name='delete-candidate-followup'),
    path('<uuid:candidate_id>/notes-followups/', get_candidate_notes_followups, name='get-candidate-notes-followups'),
    # Location search endpoints
    path('locations/search/countries/', search_countries, name='search-countries'),
    path('locations/search/states/', search_states, name='search-states'),
    path('locations/search/cities/', search_cities, name='search-cities'),
    
    path('save-step/', save_candidate_step, name='save-candidate-step'),
    path('public/filter-options/', get_public_filter_options, name='public-filter-options'),
    path('profile-tips/', get_profile_tips, name='profile-tips'),
    path('certifications/<uuid:certification_id>/upload/', upload_certification_document, name='certification-doc-upload'),





]