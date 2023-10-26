# -*- coding: utf-8 -*-
#
# Copyright (C) 2015-2020 Bitergia
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
# Authors:
#     Valerio Cosentino <valcos@bitergia.com>
#     Quan Zhou <quan@bitergia.com>
#

import json
import logging

from grimoirelab_toolkit.datetime import (datetime_to_utc,
                                          str_to_datetime)
from grimoirelab_toolkit.uris import urijoin

from perceval.backends.core.github import (GitHub,
                                           GitHubClient,
                                           GitHubCommand,
                                           DEFAULT_SLEEP_TIME,
                                           MIN_RATE_LIMIT,
                                           MAX_RETRIES,
                                           MAX_CATEGORY_ITEMS_PER_PAGE)
from ...client import HttpClient
from ...utils import DEFAULT_DATETIME, DEFAULT_LAST_DATETIME

CATEGORY_EVENT = "event"
CATEGORY_STARGAZER = "stargazer"
CATEGORY_FORK = "fork"

GITHUB_API_URL = "https://api.github.com"

EVENT_TYPES = [
    'ADDED_TO_PROJECT_EVENT',
    'MOVED_COLUMNS_IN_PROJECT_EVENT',
    'REMOVED_FROM_PROJECT_EVENT',
    'CROSS_REFERENCED_EVENT',
    'LABELED_EVENT',
    'UNLABELED_EVENT',
    'CLOSED_EVENT',
    'REOPENED_EVENT',
    'ASSIGNED_EVENT',
    'UNASSIGNED_EVENT',
    'MILESTONED_EVENT',
    'DEMILESTONED_EVENT',
    'MARKED_AS_DUPLICATE_EVENT',
    'TRANSFERRED_EVENT',
    'RENAMED_TITLE_EVENT'
]

MERGED_EVENT = 'MERGED_EVENT'

PULL_REQUEST_REVIEW_EVENT = 'PULL_REQUEST_REVIEW'

QUERY_MERGED_EVENT = """
... on MergedEvent {
  actor {
    login
  },
  id
  createdAt
  pullRequest {
    closed
    closedAt
    createdAt
    merged
    mergedAt
    updatedAt
    url
  }
  url
}
"""

QUERY_PULL_REQUEST_REVIEWS_EVENT = """
... on PullRequestReview {
  state
  body
  createdAt
  id
  pullRequest {
    closed
    closedAt
    createdAt
    merged
    mergedAt
    updatedAt
    url
  }
  url
  author{
    login
  }
}
"""
QUERY_TEMPLATE = """
    {
      repository (owner: "%s"
                  name: "%s") {
        %s (number: %s) {
          timelineItems (first: %s
                         after: %s
                         itemTypes: %s
                         since: "%s") {
              nodes {
                eventType: __typename
                ... on CrossReferencedEvent {
                  actor {
                    login
                  }
                  id
                  createdAt
                  isCrossRepository
                  willCloseTarget
                  url
                  source {
                    type:__typename
                    ... on Issue {
                      number
                      url
                      createdAt
                      updatedAt
                      closed
                      closedAt
                    },
                    ... on PullRequest {
                      number
                      url
                      createdAt
                      updatedAt
                      closed
                      closedAt
                      merged
                      mergedAt
                    }
                  }
                }
                ... on ClosedEvent {
                  actor {
                    login
                  }
                  id
                  createdAt
                  url
                  closer {
                    type:__typename
                    ... on PullRequest {
                      number
                      url
                      createdAt
                      updatedAt
                      closed
                      closedAt
                      merged
                      mergedAt
                      author {
                        login
                      }
                    }
                  }
                }
                ... on LabeledEvent {
                  actor {
                    login
                  }
                  id
                  createdAt
                  label {
                    name
                    description
                    createdAt
                    isDefault
                    updatedAt
                  }
                }
                ... on UnlabeledEvent {
                  actor {
                    login
                  }
                  id
                  createdAt
                  label {
                    name
                    description
                    createdAt
                    isDefault
                    updatedAt
                  }
                }
                ... on AddedToProjectEvent {
                  actor {
                    login
                  }
                  id
                  createdAt
                  projectColumnName,
                  project {
                    name
                    url
                    createdAt
                    updatedAt
                    closedAt
                    state
                  }
                }
                ... on MovedColumnsInProjectEvent {
                  actor {
                    login
                  },
                  id
                  createdAt
                  previousProjectColumnName
                  projectColumnName
                  project {
                    name
                    url
                    createdAt
                    updatedAt
                    closedAt
                    state
                  }
                }
                ... on RemovedFromProjectEvent {
                  actor {
                    login
                  },
                  id
                  createdAt
                  projectColumnName
                  project {
                    name
                    url
                    createdAt
                    updatedAt
                    closedAt
                    state
                  }
                }
                ... on ReopenedEvent {
                  actor {
                    login
                  }
                  id
                  createdAt
                  stateReason
                  closable {
                    closed
                    closedAt
                    viewerCanClose
                    viewerCanReopen
                  }
                }
                ... on AssignedEvent {
                  actor {
                    login
                  }
                  assignee{
                    User:  __typename
                    ... on User{
                      id
                      login
                    }
                  }
                  id
                  createdAt
                }
                ... on UnassignedEvent{
                  actor{
                    login
                  }
                  assignee{
                    User:  __typename
                    ... on User{
                      id
                      login
                    }
                  }
                  id
                  createdAt
                }
                ... on MilestonedEvent {
                  actor {        
                    login
                  }
                  id
                  createdAt
                  milestoneTitle
                  subject {
                    __typename
                    ... on Issue {
                      number
                      url
                      createdAt
                      updatedAt
                      closed
                      closedAt
                    }
                    ... on PullRequest {
                      number
                      url
                      createdAt
                      updatedAt
                      closed
                      closedAt
                      merged
                      mergedAt
                    }
                  }
                }  
                ... on DemilestonedEvent{
                  actor{
                    login
                  }
                  id
                  createdAt
                  milestoneTitle
                  subject {
                    __typename
                    ... on Issue {
                      number
                      url
                      createdAt
                      updatedAt
                      closed
                      closedAt
                    }
                    ... on PullRequest {
                      number
                      url
                      createdAt
                      updatedAt
                      closed
                      closedAt
                      merged
                      mergedAt
                    }
                  }
                }
                ... on MarkedAsDuplicateEvent {
                  actor {        
                    login
                  }
                  id
                  createdAt
                  canonical{
                    __typename
                        ... on Issue {
                          number
                          url
                          createdAt
                          updatedAt
                          closed
                          closedAt
                        }
                        ... on PullRequest {
                          number
                          url
                          createdAt
                          updatedAt
                          closed
                          closedAt
                          merged
                          mergedAt
                        }
                  }
                  isCrossRepository
                }
                ... on TransferredEvent {
                  actor {        
                    login
                  }
                  id
                  createdAt
                  fromRepository {
                    id
                    url
                    name
                  }
                } 
                ... on RenamedTitleEvent{
                actor{
                  login
                }
                id
                createdAt
                currentTitle
                previousTitle
              }
                %s
                %s
              }
              pageInfo {
                hasNextPage
                endCursor
              }
          }
        }
      }
    }
    """


QUERY_STARGAZERS_TEMPLATE = """
{ 
 repository(owner: "%s", name: "%s"){  
    stargazers(first: %s, after: %s) {
      edges {
        node {
          id
          login
          name
          email
          company
        }
        starredAt
      }
      pageInfo {
        hasNextPage
        endCursor
      }
    }
  }
}
"""


QUERY_FORKS_TEMPLATE = """
{ 
 repository(owner: "%s", name:"%s"){
    forks(first: %s, after: %s) {
      edges {
        node {
          id
          url
          createdAt
          owner {
            id
            login
          }
        }
      }
      pageInfo {
        hasNextPage
        endCursor
      }
    }
  }
}
"""

logger = logging.getLogger(__name__)


class GitHubQL(GitHub):
    """GitHubQL backend for Perceval using the GitHub API v4.
    Most of the methods are inherited from the GitHub backend.

    This class allows the fetch the issue events of a GitHub
    repository. Note that the events retrieved included also the
    ones of pull requests, since in GitHub, every pull request
    is an issue, but an issue may not be a pull request. Pull
    requests can be identified by the attribute `pull_request`
    included in `data.issue`.

    Due to the limitation of not fetching issue events after a
    given date from GitHub v3, the events are fetched via the
    GitHub v4 (based on GraphQL).

    All issues of a given tracker are retrieved in ascending order
    based on the last time they were updated. For each issue, its
    events (optionally from/until a given date) are collected using
    a GraphQL call. Each event is returned by Perceval together
    with the corresponding issue (available in data.issue).

    Since the events are collected issue by issue, the incremental
    fetching is not supported. This limitation is due to the fact
    that events that occur on an issue may not update the issue
    attributes. Since there is no way to identify new events from
    the attributes of an issue, all issues must be fetched for
    every execution.

    No user information beyond the login is included in data
    returned by this backend. Thus, the backend doesn't require
    filter classified support.

    :param owner: GitHub owner
    :param repository: GitHub repository from the owner
    :param api_token: list of GitHub auth tokens to access the API
    :param github_app_id: GitHub App ID
    :param github_app_pk_filepath: GitHub App private key PEM file path
    :param base_url: GitHub URL in enterprise edition case;
        when no value is set the backend will be fetch the data
        from the GitHub public site.
    :param tag: label used to mark the data
    :param archive: archive to store/retrieve items
    :param sleep_for_rate: sleep until rate limit is reset
    :param min_rate_to_sleep: minimum rate needed to sleep until
         it will be reset
    :param max_retries: number of max retries to a data source
        before raising a RetryError exception
    :param max_items: max number of category items per query
    :param sleep_time: time to sleep in case
        of connection problems
    :param ssl_verify: enable/disable SSL verification
    """
    version = '0.4.0'

    CATEGORIES = [CATEGORY_EVENT, CATEGORY_STARGAZER, CATEGORY_FORK]

    def __init__(self, owner=None, repository=None,
                 api_token=None, github_app_id=None, github_app_pk_filepath=None,
                 base_url=None, tag=None, archive=None,
                 sleep_for_rate=False, min_rate_to_sleep=MIN_RATE_LIMIT,
                 max_retries=MAX_RETRIES, sleep_time=DEFAULT_SLEEP_TIME,
                 max_items=MAX_CATEGORY_ITEMS_PER_PAGE, ssl_verify=True):
        super().__init__(owner, repository, api_token, github_app_id,
                         github_app_pk_filepath, base_url, tag, archive,
                         sleep_for_rate, min_rate_to_sleep, max_retries,
                         sleep_time, max_items, ssl_verify)

    def fetch(self, category=CATEGORY_EVENT, from_date=DEFAULT_DATETIME, to_date=DEFAULT_LAST_DATETIME):
        """Fetch the issue events from the repository.

        The method retrieves, from a GitHub repository, the issue events
        since/until a given date.

        :param category: the category of items to fetch
        :param from_date: obtain issue events since this date
        :param to_date: obtain issue events until this date (included)

        :returns: a generator of events
        """
        if not from_date:
            from_date = DEFAULT_DATETIME
        if not to_date:
            to_date = DEFAULT_LAST_DATETIME

        from_date = datetime_to_utc(from_date)
        to_date = datetime_to_utc(to_date)

        kwargs = {
            'from_date': from_date,
            'to_date': to_date
        }
        items = super().fetch(category, **kwargs)

        return items

    def fetch_items(self, category, **kwargs):
        """Fetch the items

        :param category: the category of items to fetch
        :param kwargs: backend arguments

        :returns: a generator of items
        """
        from_date = kwargs['from_date']
        to_date = kwargs['to_date']

        if category == CATEGORY_EVENT:
          items = self.__fetch_events(from_date, to_date)
        elif category == CATEGORY_STARGAZER:
          items = self.__fetch_stargazers(to_date)
        elif category == CATEGORY_FORK:
          items = self.__fetch_forks(to_date)
          
        return items

    @classmethod
    def has_resuming(cls):
        """Returns whether it supports to resume the fetch process.

        :returns: this backend doesn't support items resuming
        """
        return False

    @staticmethod
    def metadata_id(item):
        """Extracts the identifier from a GitHub item."""

        return str(item['id'])

    @staticmethod
    def metadata_updated_on(item):
        """Extracts the update time from a GitHub item.

        The timestamp used is extracted from 'createdAt' field.
        This date is converted to UNIX timestamp format. As GitHub
        dates are in UTC the conversion is straightforward.

        :param item: item generated by the backend

        :returns: a UNIX timestamp
        """
        ts = item['createdAt']
        ts = str_to_datetime(ts)

        return ts.timestamp()

    @staticmethod
    def metadata_category(item):
        """Extracts the category from a GitHub item.

        This backend generates one type item which is
        'event'.
        """
        if item.get('category') is None: 
          category = CATEGORY_EVENT
        elif item['category'] == CATEGORY_STARGAZER:
          category = CATEGORY_STARGAZER
        elif item['category'] == CATEGORY_FORK:
          category = CATEGORY_FORK
        else:
          category = CATEGORY_EVENT

        return category

    def _init_client(self, from_archive=False):
        """Init client"""

        return GitHubQLClient(self.owner, self.repository, self.api_token,
                              self.github_app_id, self.github_app_pk_filepath, self.base_url,
                              self.sleep_for_rate, self.min_rate_to_sleep,
                              self.sleep_time, self.max_retries, self.max_items,
                              self.archive, from_archive, self.ssl_verify)

    def __fetch_events(self, from_date, to_date):
        """Fetch the events declared at EVENT_TYPES for issues (including pull requests)"""

        issues_groups = self.client.issues(from_date=from_date)

        for raw_issues in issues_groups:
            issues = json.loads(raw_issues)
            for issue in issues:
                issue_number = issue['number']

                is_pull = 'pull_request' in issue
                events_groups = self.client.events(issue_number, is_pull, from_date)
                for events in events_groups:
                    for event in events:

                        if str_to_datetime(event['createdAt']) > to_date:
                            return

                        event['issue'] = issue
                        yield event

    def __fetch_stargazers(self, to_date):
      """ Fetch the stargazers """
      stargazers_groups = self.client.stargazers()
      for stargazers in stargazers_groups:
        for stargazer in stargazers:

            if str_to_datetime(stargazer['starredAt']) > to_date:
                return
            stargazer_node = stargazer["node"]
            stargazer_node['starredAt'] = stargazer['starredAt']
            stargazer_node['createdAt'] = stargazer['starredAt']
            stargazer_node['category'] = CATEGORY_STARGAZER
            yield stargazer_node


    def __fetch_forks(self, to_date):
      """ Fetch the fork """
      forks_groups = self.client.forks()
      for forks in forks_groups:
        for fork in forks:

            if str_to_datetime(fork["node"]['createdAt']) > to_date:
                return
            fork_node = fork["node"]
            fork_node['category'] = CATEGORY_FORK
            yield fork_node

class GitHubQLClient(GitHubClient):
    """Client for retrieving information from GitHub API

    :param owner: GitHub owner
    :param repository: GitHub repository from the owner
    :param tokens: list of GitHub auth tokens to access the API
    :param github_app_id: GitHub App ID
    :param github_app_pk_filepath: GitHub App private key PEM file path
    :param base_url: GitHub URL in enterprise edition case;
        when no value is set the backend will be fetch the data
        from the GitHub public site.
    :param sleep_for_rate: sleep until rate limit is reset
    :param min_rate_to_sleep: minimum rate needed to sleep until
         it will be reset
    :param sleep_time: time to sleep in case
        of connection problems
    :param max_retries: number of max retries to a data source
        before raising a RetryError exception
    :param max_items: max number of category items (e.g., issues,
        pull requests) per query
    :param archive: collect events already retrieved from an archive
    :param from_archive: it tells whether to write/read the archive
    :param ssl_verify: enable/disable SSL verification
    """
    VACCEPT = 'application/vnd.github.squirrel-girl-preview,application/vnd.github.starfox-preview+json'
    VPER_PAGE = 100

    def __init__(self, owner, repository, tokens=None, github_app_id=None, github_app_pk_filepath=None,
                 base_url=None, sleep_for_rate=False, min_rate_to_sleep=MIN_RATE_LIMIT,
                 sleep_time=DEFAULT_SLEEP_TIME, max_retries=MAX_RETRIES,
                 max_items=MAX_CATEGORY_ITEMS_PER_PAGE, archive=None, from_archive=False, ssl_verify=True):
        super().__init__(owner, repository, tokens, github_app_id, github_app_pk_filepath, base_url, sleep_for_rate,
                         min_rate_to_sleep, sleep_time, max_retries, max_items, archive, from_archive, ssl_verify)

        if base_url:
            graphql_url = urijoin(base_url, 'api', 'graphql')
        else:
            graphql_url = urijoin(GITHUB_API_URL, 'graphql')

        self.graphql_url = graphql_url

    def events(self, issue_number, is_pull, from_date):
        """Get the issue events of the types declared at EVENT_TYPES from the GraphQL API

        :param issue_number: number of the issue
        :param is_pull: boolean value to identify a pull request
        :param from_date: fetch events after a given date
        """
        node_type = 'pullRequest' if is_pull else 'issue'
        aux_event_types = EVENT_TYPES
        query_merged_event = ""
        query_pull_request_reviews_event = ""
        if is_pull:
            aux_event_types = EVENT_TYPES + [MERGED_EVENT, PULL_REQUEST_REVIEW_EVENT]
            query_merged_event = QUERY_MERGED_EVENT
            query_pull_request_reviews_event = QUERY_PULL_REQUEST_REVIEWS_EVENT

        event_types = '[{}]'.format(','.join(aux_event_types))

        query = QUERY_TEMPLATE % (self.owner, self.repository, node_type, issue_number,
                                  self.VPER_PAGE, "null", event_types, from_date.isoformat(),
                                  query_merged_event, query_pull_request_reviews_event)

        has_next = True
        while has_next:
            response = self.fetch(self.graphql_url, payload=json.dumps({'query': query}), method=HttpClient.POST)

            items = response.json()
            if 'errors' in items:
                logger.error("Events not collected for issue %s in %s/%s due to: %s" %
                             (issue_number, self.owner, self.repository, items['errors'][0]['message']))
                return []

            timelines = items['data']['repository'][node_type]['timelineItems']
            nodes = timelines['nodes']
            yield nodes

            page = timelines['pageInfo']
            has_next = page['hasNextPage']
            next_cursor = page['endCursor']

            query = QUERY_TEMPLATE % (self.owner, self.repository, node_type, issue_number, self.VPER_PAGE,
                                      '"{}"'.format(next_cursor), event_types, from_date.isoformat(),
                                      query_merged_event, query_pull_request_reviews_event)
      

    def stargazers(self):
      """ Get the stargazers of the repository from the GraphQL API """
      query = QUERY_STARGAZERS_TEMPLATE % (self.owner, self.repository, self.VPER_PAGE, "null")
      has_next = True
      while has_next:
          response = self.fetch(self.graphql_url, payload=json.dumps({'query': query}), method=HttpClient.POST)

          items = response.json()
          if 'errors' in items:
              logger.error("Stargazers not collected  in %s/%s due to: %s" %
                            (self.owner, self.repository, items['errors'][0]['message']))
              return []

          stargazers = items['data']['repository']['stargazers']
          edges = stargazers['edges']
          yield edges

          page = stargazers['pageInfo']
          has_next = page['hasNextPage']
          next_cursor = page['endCursor']

          query = QUERY_STARGAZERS_TEMPLATE % (self.owner, self.repository, self.VPER_PAGE, '"{}"'.format(next_cursor))

    
    def forks(self):
      """ Get the forks of the repository from the GraphQL API """
      query = QUERY_FORKS_TEMPLATE % (self.owner, self.repository, self.VPER_PAGE, "null")
      has_next = True
      while has_next:
          response = self.fetch(self.graphql_url, payload=json.dumps({'query': query}), method=HttpClient.POST)

          items = response.json()
          if 'errors' in items:
              logger.error("Forks not collected  in %s/%s due to: %s" %
                            (self.owner, self.repository, items['errors'][0]['message']))
              return []

          stargazers = items['data']['repository']['forks']
          edges = stargazers['edges']
          yield edges

          page = stargazers['pageInfo']
          has_next = page['hasNextPage']
          next_cursor = page['endCursor']

          query = QUERY_FORKS_TEMPLATE % (self.owner, self.repository, self.VPER_PAGE, '"{}"'.format(next_cursor))


class GitHubQLCommand(GitHubCommand):
    """Class to run GitHubQL backend from the command line."""

    BACKEND = GitHubQL
