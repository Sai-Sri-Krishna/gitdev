export default async function handler(req, res) {
  const { username } = req.query;

  if (!username) {
    return res.status(400).json({ error: "Username is required" });
  }

  try {
    // Safely uses the GITHUB_TOKEN from your Vercel Dashboard
    const githubResponse = await fetch(`https://api.github.com/users/${username}`, {
      headers: {
        Authorization: `Bearer ${process.env.GITHUB_TOKEN}`,
      },
    });

    if (!githubResponse.ok) {
      return res.status(githubResponse.status).json({ error: "GitHub user not found" });
    }

    const githubData = await githubResponse.json();

    // Sends the card layout and details back to your index.html file
    return res.status(200).json({
      ...githubData,
      agent_narration: `Analyzed profile for ${githubData.name || username}. They have ${githubData.public_repos} repositories and ${githubData.followers} followers.`,
      html: `
        <div class="glass p-6 rounded-xl text-center space-y-4 max-w-sm mx-auto border border-gray-700 bg-gray-950">
          <img src="${githubData.avatar_url}" class="w-24 h-24 rounded-full mx-auto border-2 border-green-500 shadow-md" />
          <div>
            <h2 class="text-xl font-bold text-white">${githubData.name || githubData.login}</h2>
            <p class="text-sm text-gray-400">@${githubData.login}</p>
          </div>
          <p class="text-xs text-gray-300 italic">"${githubData.bio || 'No bio available'}"</p>
          <div class="grid grid-cols-2 gap-2 text-xs pt-2">
            <div class="bg-gray-900 p-2 rounded">📦 Repos: <strong>${githubData.public_repos}</strong></div>
            <div class="bg-gray-900 p-2 rounded">👥 Followers: <strong>${githubData.followers}</strong></div>
          </div>
        </div>
      `
    });
  } catch (error) {
    return res.status(500).json({ error: "Internal Server Error" });
  }
}