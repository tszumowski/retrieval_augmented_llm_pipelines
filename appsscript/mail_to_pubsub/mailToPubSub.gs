/*
Derived from:
https://github.com/rasalt/telehealthGsuiteHcapi/blob/main/appscript/pubsubmsg.gs
Apache 2.0
*/

function foobar() {
  // User config
  const projectId = "[PROJECT_NAME]";
  const topicName = "embedding-indexer";
  const publishAttributes = {source: "gmail"};

  // Fetch access token
  const accessToken = ScriptApp.getOAuthToken();

  // Derive pubsub API URL
  var topicPath = "projects/" + projectId + "/topics/" + topicName;
  Logger.log(topicPath);
  var url = "https://pubsub.googleapis.com/v1/" + topicPath + ":publish";
  Logger.log(url);

  // Build the body to publish, data is base64 encoded according to docs
  // https://cloud.google.com/pubsub/docs/publisher#message_format
  message = "Hello world!";
  var body = {
    messages: [
      {
        data: Utilities.base64Encode(message),
        attributes: publishAttributes
      },
    ],
  };

  // Send the POST
  var response = UrlFetchApp.fetch(url, {
    method: "POST",
    contentType: "application/json",
    muteHttpExceptions: true,
    payload: JSON.stringify(body),
    headers: {
      Authorization: "Bearer " + accessToken,
    },
    params: JSON.stringify({ topic: topicPath }),
  });

  // Look at the results
  Logger.log("Response: " + response);
}

function forwardGmailToPubSub() {
  // User config
  const projectId = "[PROJECT_NAME]";
  const topicName = "embedding-indexer";
  const processLabel = "#indexme";
  const alreadyProcessedLabel = "#indexme-processed";

  // Fetch access token
  const accessToken = ScriptApp.getOAuthToken();

  // Get all emails with the label "#indexme"
  var labelObject = GmailApp.getUserLabelByName("#indexme");
  var threads = labelObject.getThreads();
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
      }
    }

    // Only process ones that have the tag and haven't been processed before
    if (labelFound & !processedAlready) {
      var message = thread.getMessages()[0];
      var subject = message.getSubject();
      var sender = message.getFrom();
      var body = message.getPlainBody();

      // Create the Pub/Sub message payload
      Logger.log(
        "Found unprocessed email with label: " +
          label +
          ", sender: " +
          sender +
          ", subject: " +
          subject
      );

      // Send the message to the Pub/Sub topic
      Logger.log("Sending to pub/sub topic: " + topicName);

      /*
      Derived from:
      https://github.com/rasalt/telehealthGsuiteHcapi/blob/main/appscript/pubsubmsg.gs
      Apache 2.0
      */

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
        sender: sender
      };

      // Build the body to publish, data is base64 encoded according to docs
      // https://cloud.google.com/pubsub/docs/publisher#message_format
      var pubBody = {
        messages: [
          {
            data: Utilities.base64Encode(payload),
            attributes: publishAttributes
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

      // Look at the results
      Logger.log("Response: " + response);

      // Add the "processed" label to the thread
      var processedLabelObject = GmailApp.getUserLabelByName(
        alreadyProcessedLabel
      );
      thread.addLabel(processedLabelObject);

      // Remove the indexing label from the thread
      thread.removeLabel(labelObject);

      // Archive it now that it's processed
      thread.moveToArchive();
    }
  }
}
