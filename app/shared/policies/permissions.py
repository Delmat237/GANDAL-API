from app.shared.models import User, Student, Teacher, VM, Requete


class AuthorizationPolicy:

    @staticmethod
    def is_admin_or_superadmin(user: User) -> bool:
        """Vérifie si l'utilisateur est un enseignant avec des droits d'administration."""
        if isinstance(user, Teacher):
            return user.role in ["Admin", "SuperAdmin"]
        return False

    @staticmethod
    def is_student(user: User) -> bool:
        """Vérifie si l'utilisateur est un étudiant."""
        return isinstance(user, Student)

    @staticmethod
    def can_manage_vm(user: User, vm: VM) -> bool:
        """
        Détermine si un utilisateur a le droit de gérer une VM spécifique.
        - Le propriétaire (étudiant ou enseignant) peut gérer sa VM.
        - Un Admin/SuperAdmin peut gérer toutes les VMs.
        """
        if vm.user_id == user.id:
            return True
        return AuthorizationPolicy.is_admin_or_superadmin(user)

    @staticmethod
    def can_evaluate_requests(user: User) -> bool:
        """Admin/SuperAdmin peuvent évaluer toute requête."""
        return AuthorizationPolicy.is_admin_or_superadmin(user)

    @staticmethod
    def can_evaluate_request(user: User, requete: Requete) -> bool:
        """Enseignant assigné ou Admin/SuperAdmin peut valider/rejeter."""
        if AuthorizationPolicy.is_admin_or_superadmin(user):
            return True
        if isinstance(user, Teacher):
            return requete.teacher_id == user.id
        return False

    @staticmethod
    def can_view_request(user: User, requete: Requete) -> bool:
        """
        Un étudiant ne peut voir que les requêtes qu'il a envoyées.
        Un enseignant peut voir les requêtes qui lui sont destinées ou toutes s'il est admin.
        """
        if isinstance(user, Student):
            return requete.student_id == user.id
        elif isinstance(user, Teacher):
            return requete.teacher_id == user.id or AuthorizationPolicy.is_admin_or_superadmin(user)
        return False
