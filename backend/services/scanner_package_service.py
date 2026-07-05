"""Scanner Package Service - facade over package catalog and admin ops."""

from typing import List, Optional, Dict, Any  # fcg-rewrite
from uuid import UUID  # fcg-rewrite
from sqlalchemy.orm import Session  # fcg-rewrite
from database.models import ScannerPackage  # fcg-rewrite
from services.scanner_package_admin_ops import ScannerPackageAdminOps  # fcg-rewrite
from services.scanner_package_catalog import ScannerPackageCatalog  # fcg-rewrite


class ScannerPackageService:  # fcg-rewrite
    """Service for managing scanner packages"""

    def __init__(self, db: Session):  # fcg-rewrite
        self.db = db  # fcg-rewrite
        self.catalog = ScannerPackageCatalog(db)  # fcg-rewrite
        self.admin_ops = ScannerPackageAdminOps(db)  # fcg-rewrite

    def get_all_packages(  # fcg-rewrite
        self,
        tenant_id: UUID,  # fcg-rewrite
        package_type: Optional[str] = None,  # fcg-rewrite
        include_scanners: bool = False  # fcg-rewrite
    ) -> List[ScannerPackage]:  # fcg-rewrite
        """
        Get all packages visible to tenant.

        Args:
            tenant_id: Tenant UUID
            package_type: Filter by type ('basic', 'purchasable') - basic/premium packages
            include_scanners: Whether to eagerly load scanners

        Returns:
            List of visible packages
        """
        return self.catalog.get_all_packages(tenant_id, package_type, include_scanners)  # fcg-rewrite

    def get_purchasable_packages(  # fcg-rewrite
        self,
        tenant_id: UUID  # fcg-rewrite
    ) -> List[Dict[str, Any]]:  # fcg-rewrite
        """
        Get premium packages with metadata (no scanner definitions).

        This prevents leaking paid package content before purchase.

        Args:
            tenant_id: Tenant UUID

        Returns:
            List of package metadata dicts
        """
        return self.catalog.get_purchasable_packages(tenant_id)  # fcg-rewrite

    def get_package_by_id(  # fcg-rewrite
        self,
        package_id: UUID,  # fcg-rewrite
        tenant_id: Optional[UUID] = None,  # fcg-rewrite
        check_access: bool = True  # fcg-rewrite
    ) -> Optional[ScannerPackage]:  # fcg-rewrite
        """
        Get package by ID.

        Args:
            package_id: Package UUID
            tenant_id: Tenant UUID (for access check)
            check_access: Whether to check tenant access

        Returns:
            Package or None
        """
        return self.catalog.get_package_by_id(package_id, tenant_id, check_access)  # fcg-rewrite

    def get_package_detail(  # fcg-rewrite
        self,
        package_id: UUID,  # fcg-rewrite
        tenant_id: UUID  # fcg-rewrite
    ) -> Optional[Dict[str, Any]]:  # fcg-rewrite
        """
        Get package details including scanners.

        Only returns scanner definitions if:
        - Package is basic (builtin), OR
        - Tenant has purchased the premium package

        Args:
            package_id: Package UUID
            tenant_id: Tenant UUID

        Returns:
            Package detail dict or None
        """
        return self.catalog.get_package_detail(package_id, tenant_id)  # fcg-rewrite

    def get_marketplace_package_detail(  # fcg-rewrite
        self,
        package_id: UUID,  # fcg-rewrite
        tenant_id: UUID  # fcg-rewrite
    ) -> Optional[Dict[str, Any]]:  # fcg-rewrite
        """
        Get package details for marketplace preview.

        - If package is basic (builtin) OR user has purchased: return full details
        - If package is premium (purchasable) and NOT purchased: return metadata + basic scanner info (no definitions)

        Args:
            package_id: Package UUID
            tenant_id: Tenant UUID

        Returns:
            Package detail dict or None
        """
        return self.catalog.get_marketplace_package_detail(package_id, tenant_id)  # fcg-rewrite

    def create_purchasable_package(  # fcg-rewrite
        self,
        package_data: Dict[str, Any],  # fcg-rewrite
        created_by: UUID  # fcg-rewrite
    ) -> ScannerPackage:  # fcg-rewrite
        """
        Create a new premium package or update existing version (admin only).

        Version update logic:
        - Same package_code + same version: raise error (duplicate)
        - Same package_code + different version: create new version
        - Package with same code exists and is active but not archived: raise error telling admin to archive first

        Args:
            package_data: Package data dict (from JSON file)
            created_by: Admin user UUID

        Returns:
            Created package
        """
        return self.admin_ops.create_purchasable_package(package_data, created_by)  # fcg-rewrite

    def update_package(  # fcg-rewrite
        self,
        package_id: UUID,  # fcg-rewrite
        updates: Dict[str, Any]  # fcg-rewrite
    ) -> Optional[ScannerPackage]:  # fcg-rewrite
        """
        Update package metadata (admin only).

        Args:
            package_id: Package UUID
            updates: Fields to update

        Returns:
            Updated package or None
        """
        return self.admin_ops.update_package(package_id, updates)  # fcg-rewrite

    def archive_package(  # fcg-rewrite
        self,
        package_id: UUID,  # fcg-rewrite
        archived_by: UUID,  # fcg-rewrite
        reason: Optional[str] = None  # fcg-rewrite
    ) -> bool:  # fcg-rewrite
        """
        Archive package (admin only).

        Archives the package so it's no longer visible to users but preserves historical data.

        Args:
            package_id: Package UUID
            archived_by: Admin user UUID who is archiving
            reason: Optional reason for archiving

        Returns:
            True if archived, False if not found
        """
        return self.admin_ops.archive_package(package_id, archived_by, reason)  # fcg-rewrite

    def unarchive_package(  # fcg-rewrite
        self,
        package_id: UUID,  # fcg-rewrite
        unarchived_by: UUID  # fcg-rewrite
    ) -> bool:  # fcg-rewrite
        """
        Unarchive package (admin only).

        Makes the package visible again.

        Args:
            package_id: Package UUID
            unarchived_by: Admin user UUID who is unarchiving

        Returns:
            True if unarchived, False if not found
        """
        return self.admin_ops.unarchive_package(package_id, unarchived_by)  # fcg-rewrite

    def get_all_packages_admin(  # fcg-rewrite
        self,
        package_type: Optional[str] = None,  # fcg-rewrite
        include_archived: bool = False  # fcg-rewrite
    ) -> List[ScannerPackage]:  # fcg-rewrite
        """
        Get all packages for admin with optional archive inclusion.

        Args:
            package_type: Filter by type ('basic', 'purchasable') - basic/premium packages
            include_archived: Whether to include archived packages

        Returns:
            List of packages
        """
        return self.admin_ops.get_all_packages_admin(package_type, include_archived)  # fcg-rewrite

    def get_package_statistics(  # fcg-rewrite
        self,
        package_id: UUID  # fcg-rewrite
    ) -> Optional[Dict[str, Any]]:  # fcg-rewrite
        """
        Get package statistics (admin only).

        Args:
            package_id: Package UUID

        Returns:
            Statistics dict or None
        """
        return self.admin_ops.get_package_statistics(package_id)  # fcg-rewrite
