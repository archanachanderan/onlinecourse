function confirmDelete(item = 'this') {
    return confirm(`Are you sure you want to delete ${item}?`);
}

// Auto-hide flash messages after 3 seconds
window.onload = function () {
    const flash = document.getElementById("flash-message");
    if (flash) {
        setTimeout(() => flash.style.display = "none", 3000);
    }
}
