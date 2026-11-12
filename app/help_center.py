"""Authored product help, available without a catalog or database query."""
from flask import Blueprint, abort, render_template, request

help_center = Blueprint('help_center', __name__)

TOPICS = (
    ('library', 'Your library', 'M4 4h6l2 2 2-2h6v15h-6l-2 2-2-2H4Z', (
        ('How do I add a game?', 'Open Library, choose Add game, search for a title and select a catalog result. Choose its platform and status, then save. Your rating and review are optional.'),
        ('Can I save the same game on different platforms?', 'Yes. Each platform is a separate library entry. If that game and platform are already saved, edit the existing entry instead of adding a duplicate.'),
        ('How do I choose what to play next?', 'Open Pick a game in Library. For you uses your saved taste signals; Random lets the roulette choose. The status, genre and platform selections narrow the eligible library games.'),
    )),
    ('reviews', 'Ratings & reviews', 'm12 3 3 6 6 1-4.5 4.5 1 6.5L12 18l-5.5 3 1-6.5L3 10l6-1Z', (
        ('What is the rating scale?', 'Ratings use five stars, including half stars. A rating is optional: you can save a game without choosing one.'),
        ('How do I publish a review?', 'Write your review in Add game or Edit game and select Also publish this review before saving. You can mark spoilers there too. A review left only in your library is private.'),
        ('Why does my review not appear on my public profile?', 'Only explicitly published reviews appear publicly, and your profile must be public. Private library notes are never used as a public review. Check the publication option in Edit game and your profile privacy settings.'),
    )),
    ('privacy', 'Profile & privacy', 'M12 3 4 6v6c0 5 8 9 8 9s8-4 8-9V6ZM9 12l2 2 4-4', (
        ('What can other players see?', 'Public profiles can show your bio, showcase, statistics, recent activity, badges and wishlist according to your sharing choices. Your full library, email and private notes are not exposed by your public profile.'),
        ('How do I hide part of my profile?', 'Open Edit profile and use Privacy & sharing. Public is the default; you can hide individual sections or make the whole profile private. Save changes to apply your choices.'),
        ('How do I change my photo, background or badges?', 'Use the edit icons on your player card in Edit profile. Uploaded images have a preview and crop controls. You can feature up to three earned badges; the rest remain in your collection.'),
    )),
    ('wishlist', 'Wishlist', 'M6 3h12v18l-6-4-6 4ZM9 9h6m-3-3v6', (
        ('Is a wish already part of my library?', 'No. Wishlist saves games you want to play or own later. Add the game to your library when you are ready; the matching wish is then removed automatically.'),
        ('Who can see my wishlist?', 'It is public by default when your profile is public. Edit profile includes an option to make the wishlist private. A nonempty public wishlist is available from your profile.'),
    )),
    ('discover', 'Discover', 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18Zm4 5-3 5-5 3 3-5Z', (
        ('What is the difference between For you and Popular picks?', 'For you finds catalog games that match your ratings and wishlist. Popular picks does not use your tastes. Both exclude catalog games already in your library and respect your genre and platform filters.'),
        ('How do the sorting options work?', 'Most popular uses the number of catalog ratings. Highest rated uses the catalog score and requires at least 50 ratings. Newest releases puts recent released games first. These catalog scores are separate from Vestigium player reviews.'),
        ('Why are some games or covers missing?', 'Results come from a bounded selection of catalog matches, not every game ever made. Missing artwork or platform details depend on the catalog. A final results page can have an incomplete row when no more matches remain.'),
    )),
    ('account', 'Account & access', 'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm-8 9v-2a8 8 0 0 1 16 0v2', (
        ('How do I recover my password?', 'Choose Forgot password on the sign-in page and follow the email link. Check your spam folder if it does not arrive. Never share a password or recovery link with another player.'),
        ('Does a temporary outage delete my account?', 'No. A temporary service outage or a paused database does not by itself delete your account. Try again later instead of creating a duplicate account. A site administrator must restore a paused project.'),
    )),
)


@help_center.get('/help')
def index():
    query = request.args.get('q', '').strip()
    if len(query) > 200 or '\x00' in query:
        abort(400)
    topics = []
    for key, title, icon, entries in TOPICS:
        questions = [{'question': question, 'answer': answer,
                      'matches': query.casefold() in f'{title} {question} {answer}'.casefold()}
                     for question, answer in entries]
        topics.append({'id': key, 'title': title, 'icon': icon, 'questions': questions,
                       'matches': any(item['matches'] for item in questions)})
    return render_template('help.html', topics=topics, query=query,
                           has_matches=any(topic['matches'] for topic in topics))
