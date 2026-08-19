# must change.(account models)
1. the login/authentication/... MUST be on sensitive email set. it need to
change of all the nes .
Register API
   ↓
Serializer
   ↓
UserManager.create_user()
   ↓
User.save()
   ↓
Database constraint

Login API
   ↓
authenticate()
   ↓
get_by_natural_key()

Forgot Password
   ↓
email lookup

Invitation
   ↓
email lookup
   ↓
User
   ↓
TeamMembership
