function forwardGmailToPubSub() {
  // User config
  const projectId = "liquid-champion-195421";
  const embeddingTopicName = "embedding-indexer";
  const scrapeTopicName = "url-scraper";
  const processLabel = "#indexme";
  const alreadyProcessedLabel = "#indexme-processed";
  const scrapeLabel = "#scrapeme";
  const MIN_BODY_LEN = 1000; // Replace with desired minimum body length

  // Fetch access token
  const accessToken = ScriptApp.getOAuthToken();

  // Get all emails with the label "#indexme"
  var processLabelObject = GmailApp.getUserLabelByName(processLabel);
  var scrapeLabelObject = GmailApp.getUserLabelByName(scrapeLabel);
  var threads = processLabelObject.getThreads();
  Logger.log(
    "Found " + threads.length + " candidate emails with label: " + processLabel
  );

  // Loop over all threads
  for (var i = 0; i < threads.length; i++) {
    var thread = threads[i];

    // Parse the relevant labels
    var labels = thread.getLabels();
    var processedAlready = false;
    var labelFound = false;
    var scrapeLabelFound = false;
    for (var j = 0; j < labels.length; j++) {
      if (labels[j] == null) {
        continue;
      }
      var label = labels[j].getName();
      if (label == alreadyProcessedLabel) {
        // Skip if already processed
        processedAlready = true;
        break;
      } else if (label == processLabel) {
        labelFound = true;
        continue;
      } else if (label == scrapeLabel) {
        scrapeLabelFound = true;
        continue;
      }
    }

    // Only process ones that have the tag and haven't been processed before
    if (labelFound & !processedAlready) {
      var message = thread.getMessages()[0];
      var subject = message.getSubject();
      var sender = message.getFrom();
      var body = message.getPlainBody();

      // Check if body length is greater than MIN_BODY_LEN
      if (body.length > MIN_BODY_LEN) {
        // Send the message to the Pub/Sub topic
        sendToPubSub(
          projectId,
          embeddingTopicName,
          accessToken,
          sender,
          subject,
          body
        );
      }

      // If scrapeLabel is also found, send the message to the "url-scraper" Pub/Sub topic
      if (scrapeLabelFound) {
        sendToPubSub(
          projectId,
          scrapeTopicName,
          accessToken,
          sender,
          subject,
          body
        );

        // Remove the scraping label from the thread
        thread.removeLabel(scrapeLabelObject);
      }

      // Add the "processed" label to the thread
      var processedprocessLabelObject = GmailApp.getUserLabelByName(
        alreadyProcessedLabel
      );
      thread.addLabel(processedprocessLabelObject);

      // Remove the indexing label from the thread
      thread.removeLabel(processLabelObject);

      // [COMMENTED OUT] Optional Archive, now that it's processed
      // thread.moveToArchive();
    }
  }
}

function sendToPubSub(
  projectId,
  topicName,
  accessToken,
  sender,
  subject,
  body
) {
  // Derive pubsub API URL
  var topicPath = "projects/" + projectId + "/topics/" + topicName;
  var url = "https://pubsub.googleapis.com/v1/" + topicPath + ":publish";
  var payload =
    "Sender: " +
    sender +
    "\n" +
    "Subject: " +
    subject +
    "\n" +
    "Body: \n" +
    body;

  // Build the attributes to publish
  var publishAttributes = {
    source: "gmail",
    sender: sender,
    title: subject
  };

  // Build the body to publish, data is base64 encoded according to docs
  // https://cloud.google.com/pubsub/docs/publisher#message_format
  var pubBody = {
    messages: [
      {
        data: Utilities.base64Encode(payload),
        attributes: publishAttributes,
      },
    ],
  };

  // Send the POST
  var response = UrlFetchApp.fetch(url, {
    method: "POST",
    contentType: "application/json",
    muteHttpExceptions: true,
    payload: JSON.stringify(pubBody),
    headers: {
      Authorization: "Bearer " + accessToken,
    },
    params: JSON.stringify({ topic: topicPath }),
  });
}
