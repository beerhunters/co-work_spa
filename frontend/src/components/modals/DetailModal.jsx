import React from 'react';
import BookingDetailModal from './BookingDetailModal';
import PromocodeDetailModal from './PromocodeDetailModal';
import TariffDetailModal from './TariffDetailModal';
import TicketDetailModal from './TicketDetailModal';
import UserDetailModal from './UserDetailModal';
import AdminDetailModal from "./AdminDetailModal.jsx";

const DetailModal = ({ isOpen, onClose, selectedItem, onUpdate, currentAdmin }) => {
  if (!selectedItem) return null;

  const { type } = selectedItem;

  switch (type) {
    case 'user':
      return (
        <UserDetailModal
          isOpen={isOpen}
          onClose={onClose}
          user={selectedItem}
          onUpdate={onUpdate}
        />
      );
    case 'booking':
      return (
        <BookingDetailModal
          isOpen={isOpen}
          onClose={onClose}
          booking={selectedItem}
        />
      );
    case 'tariff':
      return (
        <TariffDetailModal
          isOpen={isOpen}
          onClose={onClose}
          tariff={selectedItem}
        />
      );
    case 'promocode':
      return (
        <PromocodeDetailModal
          isOpen={isOpen}
          onClose={onClose}
          promocode={selectedItem}
        />
      );
    case 'ticket':
      return (
        <TicketDetailModal
          isOpen={isOpen}
          onClose={onClose}
          ticket={selectedItem}
          onUpdate={onUpdate}
        />
      );
    case 'admin':
      return (
        <AdminDetailModal
          isOpen={isOpen}
          onClose={onClose}
          admin={selectedItem}
          onUpdate={onUpdate}
          currentAdmin={currentAdmin}
        />
      );
    default:
      return null;
  }
};

export default DetailModal;