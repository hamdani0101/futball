const competitionSelect = document.getElementById("competition");
    if (competitionSelect) {
        //get data season per competition
        const seasonsData = JSON.parse("{{ season_json_data|escapejs }}");

        //update season options when competition changes
        competitionSelect.addEventListener("change", () => {
        const selectedCompetitionId = competitionSelect.value;
        const seasonSelect = document.getElementById("season");
        seasonSelect.innerHTML = "";
        seasonsData.forEach(s => {
            if (s.fields.competition == selectedCompetitionId) {
            const option = document.createElement("option");
            option.value = s.pk;
            option.text =  s.fields.name;
            seasonSelect.appendChild(option);
            }
        });
    });
}