import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { getNotifications, getUnreadCount, markAsRead, markAllAsRead } from "../api/notifications";

export function useNotifications() {
  const navigate = useNavigate();
  const [unreadCount, setUnreadCount] = useState(0);
  const [notifications, setNotifications] = useState([]);
  const [isOpen, setIsOpen] = useState(false);

  const fetchCount = useCallback(() => {
    getUnreadCount()
      .then((d) => setUnreadCount(d.count))
      .catch(() => {});
  }, []);

  useEffect(() => {
    fetchCount();
    const interval = setInterval(fetchCount, 30000);
    return () => clearInterval(interval);
  }, [fetchCount]);

  const openDropdown = async () => {
    try {
      const data = await getNotifications({ limit: 10 });
      setNotifications(data.data);
      setUnreadCount(data.unread_count);
    } catch {
      setNotifications([]);
    }
    setIsOpen(true);
  };

  const closeDropdown = () => setIsOpen(false);

  const handleClick = (notification) => {
    markAsRead(notification.id).catch(() => {});
    setUnreadCount((prev) => Math.max(0, notification.is_read ? prev : prev - 1));
    setNotifications((prev) =>
      prev.map((n) => (n.id === notification.id ? { ...n, is_read: true } : n))
    );
    setIsOpen(false);
    if (notification.redirect_path) {
      navigate(notification.redirect_path);
    }
  };

  const handleMarkAllAsRead = async () => {
    await markAllAsRead().catch(() => {});
    setUnreadCount(0);
    setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
  };

  return {
    unreadCount,
    notifications,
    isOpen,
    openDropdown,
    closeDropdown,
    handleClick,
    handleMarkAllAsRead,
  };
}
