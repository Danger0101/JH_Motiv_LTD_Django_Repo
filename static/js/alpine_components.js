document.addEventListener("alpine:init", () => {
  // Alpine.js function for the recurring availability editor
  Alpine.data("scheduleEditor", (initialScheduleJSON, saveUrl, csrfToken) => ({
    isSaving: false,
    message: "",
    isError: false,
    schedule: [],
    init() {
      const initialSchedule = JSON.parse(initialScheduleJSON);
      const dayNames = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
      ];
      this.schedule = dayNames.map((name, index) => ({
        name: name,
        slots: initialSchedule[index] ? [...initialSchedule[index]] : [],
      }));
    },
    addSlot(dayIndex) {
      this.schedule[dayIndex].slots.push({ start: "09:00", end: "17:00" });
    },
    removeSlot(dayIndex, slotIndex) {
      this.schedule[dayIndex].slots.splice(slotIndex, 1);
    },
    async saveSchedule() {
      this.isSaving = true;
      this.message = "";
      this.isError = false;

      for (const day of this.schedule) {
        const sortedSlots = [...day.slots].sort((a, b) =>
          a.start.localeCompare(b.start)
        );
        for (let i = 0; i < sortedSlots.length - 1; i++) {
          if (sortedSlots[i].end > sortedSlots[i + 1].start) {
            this.isError = true;
            this.message = `Error on ${day.name}: Time slots cannot overlap.`;
            this.isSaving = false;
            return;
          }
        }
      }

      try {
        const response = await fetch(saveUrl, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrfToken,
          },
          body: JSON.stringify({ schedule: this.schedule }),
        });
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.error || "An unknown error occurred.");
        }
        this.message = data.message;
        htmx.trigger("body", "recurring-schedule-updated");
      } catch (error) {
        this.isError = true;
        this.message = error.message;
      } finally {
        this.isSaving = false;
        setTimeout(() => (this.message = ""), 4000);
      }
    },
  }));

  // Alpine.js function for the offering create/edit form
  Alpine.data("offeringManager", () => ({
    isEditing: false,
    formData: {
      id: "",
      name: "",
      description: "",
      price: "",
      credits_granted: 1,
      duration_months: 3,
      is_active: true,
      is_full_day: false,
      duration_minutes: 60,
      terms_and_conditions: "",
      questions: [],
    },
    resetForm() {
      this.isEditing = false;
      this.formData = {
        id: "",
        name: "",
        description: "",
        price: "",
        credits_granted: 1,
        duration_months: 3,
        is_active: true,
        is_full_day: false,
        duration_minutes: 60,
        terms_and_conditions: "",
        questions: [],
      };
    },
    editOffering(offeringId) {
      const dataScript = document.getElementById(`offering-data-${offeringId}`);
      if (dataScript) {
        const data = JSON.parse(dataScript.textContent);
        this.isEditing = true;
        this.formData = {
          ...this.formData,
          ...data,
          questions: data.questions.map((q) => ({ text: q.text })),
        };
      }
    },
    addQuestion() {
      this.formData.questions.push({ text: "" });
    },
    removeQuestion(index) {
      this.formData.questions.splice(index, 1);
    },
  }));
});
