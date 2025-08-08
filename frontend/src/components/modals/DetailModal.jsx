import React from 'react';
import UserDetailModal from './UserDetailModal';
import BookingDetailModal from './BookingDetailModal';
import TicketDetailModal from './TicketDetailModal';
import TariffDetailModal from './TariffDetailModal';
import PromocodeDetailModal from './PromocodeDetailModal';

const DetailModal = ({ isOpen, onClose, selectedItem, onUpdate }) => {
  if (!selectedItem) return null;

  const { type, ...item } = selectedItem;

  switch (type) {
    case 'user':
      return (
        <UserDetailModal
          isOpen={isOpen}
          onClose={onClose}
          user={item}
          onUpdate={onUpdate}
        />
      );

    case 'booking':
      return (
        <BookingDetailModal
          isOpen={isOpen}
          onClose={onClose}
          booking={item}
        />
      );

    case 'ticket':
      return (
        <TicketDetailModal
          isOpen={isOpen}
          onClose={onClose}
          ticket={item}
        />
      );

    case 'tariff':
      return (
        <TariffDetailModal
          isOpen={isOpen}
          onClose={onClose}
          tariff={item}
        />
      );

    case 'promocode':
      return (
        <PromocodeDetailModal
          isOpen={isOpen}
          onClose={onClose}
          promocode={item}
        />
      );

    default:
      return null;
  }
};

export default DetailModal;